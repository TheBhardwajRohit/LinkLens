"""Fingerprints: short codes that stay almost the same when a page is copied with small changes.

Scammers reuse kits, so two pages from the same kit get close fingerprints even on different
domains. Five kinds are taken (see docs/TECH_DECISIONS.md for why each):

- tlsh          fuzzy hash of the HTML; a small distance means near-identical code
- dom_hash      exact hash of the page's tag sequence (structure without the words)
- dom_simhash   64-bit "similarity hash" of the tag sequence; few differing bits means similar structure
- text_simhash  the same for the visible words
- phash         perceptual hash of the screenshot; pages that look alike get close hashes
- favicon_hash  MurmurHash3 of the site icon (the same number search engines like Shodan use)

The HTML is only read as data here (safety rules 5 and 6). Nothing is fetched.
"""

import base64
import io
import unicodedata
from collections import Counter
from hashlib import blake2b
from urllib.parse import urljoin, urlsplit

import imagehash
import mmh3
import numpy as np
import tldextract
import tlsh
from lxml import etree
from lxml import html as lxml_html
from PIL import Image, ImageStat
from pydantic import BaseModel

MAX_HTML = 2_000_000
MAX_TAGS = 6000
MAX_WORDS = 6000
MAX_TEXT = 300_000
MAX_TERMS = 40
MAX_OUT_DOMAINS = 60
MAX_FAVICON_BYTES = 200_000
THUMB_SIZE = (240, 150)

_sites = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, include_psl_private_domains=True)
_SKIPPED_TAGS = {"script", "style", "noscript", "template", "svg", "head"}
# Very common words carry no signal about which page this is.
STOPWORDS = frozenset(
    """the and for you your with this that from are was were will have has not but all can our out get
    more new one use any may who how its their they them there here what when where which while been
    about into over also than then these those such only other some very just most each per via
    und der die das mit von den que los las por para con una del est pour les des dans sur""".split()
)


class Fingerprints(BaseModel):
    tlsh: str | None = None
    dom_hash: str | None = None  # 16 hex characters
    dom_simhash: str | None = None  # 16 hex characters (64 bits)
    text_simhash: str | None = None  # 16 hex characters (64 bits)
    phash: str | None = None  # 16 hex characters (64 bits)
    favicon_hash: int | None = None  # signed 32-bit, Shodan style
    tags: int = 0
    words: int = 0
    terms: list[str] = []  # the page's most used words, for text similarity
    out_domains: list[str] = []  # other sites this page links to, for the link graph


def split_words(text: str) -> list[str]:
    """Lower-case words of 3 to 30 letters. Vowel signs and other combining marks count as part of
    the word, so Hindi, Tamil, or Bengali words stay whole."""
    words: list[str] = []
    current: list[str] = []
    for ch in text[:MAX_TEXT] + " ":
        if ch.isalpha() or (ch > "˿" and unicodedata.category(ch)[0] == "M"):
            current.append(ch)
            continue
        if 3 <= len(current) <= 30:
            words.append("".join(current).lower())
            if len(words) >= MAX_WORDS:
                break
        current = []
    return words


def _digest64(text: str) -> bytes:
    return blake2b(text.encode("utf-8", "ignore"), digest_size=8).digest()


def simhash(items: list[str]) -> str | None:
    """A 64-bit similarity hash: every item votes on each bit, and the majority wins. Two lists that
    share most items end up with hashes that differ in only a few bits."""
    if len(items) < 4:
        return None
    raw = np.frombuffer(b"".join(_digest64(i) for i in items), dtype=np.uint8).reshape(-1, 8)
    votes = np.unpackbits(raw, axis=1).sum(axis=0)
    bits = (votes * 2 > len(items)).astype(np.uint8)
    return np.packbits(bits).tobytes().hex()


def shingles(tokens: list[str], size: int = 3) -> list[str]:
    if len(tokens) < size:
        return [" ".join(tokens)] if tokens else []
    return [" ".join(tokens[i : i + size]) for i in range(len(tokens) - size + 1)]


def hamming(a: str | None, b: str | None) -> int | None:
    """How many of the 64 bits differ between two hex hashes (0 means identical)."""
    if not a or not b:
        return None
    return (int(a, 16) ^ int(b, 16)).bit_count()


def tlsh_distance(a: str | None, b: str | None) -> int | None:
    """TLSH's own distance: 0 is identical, under about 50 is near-identical code."""
    if not a or not b:
        return None
    try:
        return tlsh.diff(a, b)
    except ValueError:
        return None


def to_signed64(hex_hash: str | None) -> int | None:
    """Postgres BIGINT is signed, so the top bit becomes the sign."""
    if not hex_hash:
        return None
    value = int(hex_hash, 16)
    return value - (1 << 64) if value >= (1 << 63) else value


def from_signed64(value: int | None) -> str | None:
    if value is None:
        return None
    return f"{value + (1 << 64) if value < 0 else value:016x}"


def _parse(html: str):
    # Hand lxml UTF-8 bytes and say so. Given a plain string, it guesses the encoding from the
    # page's own tags and can turn non-English text into garbage.
    try:
        parser = lxml_html.HTMLParser(encoding="utf-8")
        return lxml_html.fromstring(html.encode("utf-8", "ignore"), parser=parser)
    except (etree.ParserError, ValueError):
        return None


def _site(host: str) -> str | None:
    return _sites(host).top_domain_under_public_suffix or host or None


def html_fingerprints(html: str | None, page_url: str | None = None) -> Fingerprints:
    fp = Fingerprints()
    if not html or len(html) < 50:
        return fp
    html = html[:MAX_HTML]

    data = html.encode("utf-8", "ignore")
    code = tlsh.hash(data)
    fp.tlsh = code if code and code != "TNULL" else None

    root = _parse(html)
    if root is None:
        return fp

    tags = [el.tag for el in root.iter() if isinstance(el.tag, str)][:MAX_TAGS]
    fp.tags = len(tags)
    if len(tags) >= 8:
        fp.dom_hash = blake2b(" ".join(tags).encode(), digest_size=8).hexdigest()
        fp.dom_simhash = simhash(shingles(tags, 4))

    # Links out, before the text pass removes anything.
    if page_url:
        own = _site((urlsplit(page_url).hostname or "").lower())
        out: dict[str, None] = {}
        for href in root.xpath("//a/@href")[:2000]:
            href = str(href).strip()
            if not href.lower().startswith(("http://", "https://", "//")):
                continue
            try:
                host = (urlsplit(urljoin(page_url, href)).hostname or "").lower()
            except ValueError:
                continue
            site = _site(host) if host else None
            if site and site != own and "." in site:
                out[site] = None
                if len(out) >= MAX_OUT_DOMAINS:
                    break
        fp.out_domains = list(out)

    for el in [e for e in root.iter() if isinstance(e.tag, str) and e.tag in _SKIPPED_TAGS]:
        if el.getparent() is not None:
            el.drop_tree()
    words = split_words(root.text_content() or "")
    fp.words = len(words)
    if len(words) >= 12:
        fp.text_simhash = simhash(shingles(words, 3))
        counts = Counter(w for w in words if w not in STOPWORDS)
        fp.terms = [w for w, _ in counts.most_common(MAX_TERMS)]
    return fp


def _open_image(jpeg_b64: str | None) -> Image.Image | None:
    if not jpeg_b64:
        return None
    try:
        image = Image.open(io.BytesIO(base64.b64decode(jpeg_b64)))
        image.load()
        return image.convert("RGB")
    except Exception:
        return None


def screenshot_phash(jpeg_b64: str | None) -> str | None:
    """Perceptual hash of our own screenshot. Blank or single-color pages are skipped, because they
    would all "match" each other."""
    image = _open_image(jpeg_b64)
    if image is None:
        return None
    if max(ImageStat.Stat(image.convert("L")).stddev) < 6:
        return None
    return str(imagehash.phash(image))


def thumbnail(jpeg_b64: str | None) -> bytes | None:
    """A small picture of the page (a few kB), kept after the full screenshot is gone."""
    image = _open_image(jpeg_b64)
    if image is None:
        return None
    image = image.crop((0, 0, image.width, min(image.height, int(image.width * 0.625))))
    image.thumbnail(THUMB_SIZE)
    out = io.BytesIO()
    image.save(out, "JPEG", quality=45, optimize=True)
    return out.getvalue()


def favicon_hash(icon_b64: str | None) -> int | None:
    """MurmurHash3 of the icon's bytes, encoded the way Shodan does it, so the number can be looked
    up elsewhere. The icon is only hashed, never opened as an image."""
    if not icon_b64:
        return None
    try:
        raw = base64.b64decode(icon_b64)
    except ValueError:
        return None
    if not raw or len(raw) > MAX_FAVICON_BYTES:
        return None
    return mmh3.hash(base64.encodebytes(raw))


def fingerprint_visit(visit: dict) -> Fingerprints:
    """All fingerprints for one sandbox visit."""
    fp = html_fingerprints(visit.get("html"), visit.get("final_url"))
    fp.phash = screenshot_phash(visit.get("screenshot_jpeg_b64"))
    fp.favicon_hash = favicon_hash(visit.get("favicon_b64"))
    return fp

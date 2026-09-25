"""Clues in the link itself, before looking at the page: lookalike names, odd structure, and tricks."""

import ipaddress
import math
import re
from collections import Counter
from urllib.parse import urlsplit

import tldextract
from pydantic import BaseModel
from rapidfuzz.distance import DamerauLevenshtein

from app.analysis.brands import Brand, brands, official_name
from app.analysis.toplist import toplist

_public = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)
# Also knows "private" suffixes like github.io, so user.github.io counts as its own site.
_sites = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, include_psl_private_domains=True)

SHORTENERS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "goo.gl",
    "ow.ly",
    "is.gd",
    "cutt.ly",
    "rb.gy",
    "tiny.cc",
    "shorturl.at",
    "rebrand.ly",
    "bit.do",
    "s.id",
    "t.ly",
    "v.gd",
    "qrco.de",
    "shorturl.asia",
    "tiny.one",
    "bl.ink",
    "lnkd.in",
    "surl.li",
    "u.to",
    "clck.ru",
    "bitly.ws",
    "short.io",
    "linktr.ee",
    "urlz.fr",
    "shorte.st",
}
# TLDs that security reports keep finding over-represented in abuse. A heuristic, not proof.
ABUSED_TLDS = {
    "zip",
    "mov",
    "xyz",
    "top",
    "icu",
    "click",
    "gq",
    "tk",
    "ml",
    "cf",
    "ga",
    "buzz",
    "rest",
    "monster",
    "cyou",
    "sbs",
    "cfd",
    "lol",
    "bond",
    "quest",
    "support",
    "live",
    "shop",
    "online",
    "site",
    "fun",
    "win",
    "loan",
    "work",
    "cam",
    "bar",
    "email",
    "info",
}
URL_WORDS = {
    "login",
    "signin",
    "sign-in",
    "logon",
    "verify",
    "verification",
    "update",
    "secure",
    "security",
    "account",
    "kyc",
    "banking",
    "netbanking",
    "wallet",
    "bonus",
    "gift",
    "prize",
    "reward",
    "otp",
    "refund",
    "suspend",
    "suspended",
    "unlock",
    "confirm",
    "support",
    "helpdesk",
    "recover",
    "recovery",
    "reactivate",
    "claim",
    "challan",
    "aadhaar",
    "pan",
    "upi",
    "free",
    "win",
    "winner",
    "invoice",
    "payment",
    "billing",
}
# Characters that look like Latin letters (other alphabets), plus common digit swaps.
CONFUSABLES = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "х": "x",
        "у": "y",
        "і": "i",
        "ј": "j",
        "ԁ": "d",
        "һ": "h",
        "ӏ": "l",
        "ѕ": "s",
        "ԛ": "q",
        "ԝ": "w",
        "ɡ": "g",
        "ո": "n",
        "ս": "u",
        "ο": "o",
        "ρ": "p",
        "ν": "v",
        "τ": "t",
        "κ": "k",
        "α": "a",
        "ε": "e",
        "ι": "i",
        "ı": "i",
        "ł": "l",
        "0": "o",
        "1": "l",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "8": "b",
        "9": "g",
    }
)


class Lookalike(BaseModel):
    brand: str
    category: str
    kind: str  # homograph | typo | combo | subdomain
    detail: str


class LinkFeatures(BaseModel):
    url: str
    host: str
    unicode_host: str | None = None  # set when the host uses punycode (xn--)
    registered_domain: str | None = None
    site: str | None = None  # like registered_domain, but user.github.io stays user.github.io
    suffix: str | None = None
    free_hosting: str | None = None  # e.g. "github.io"
    is_ip: bool = False
    port: int | None = None
    length: int = 0
    subdomain_depth: int = 0
    digit_ratio: float = 0.0
    hyphens: int = 0
    entropy: float = 0.0
    has_at: bool = False
    double_slash_path: bool = False
    abused_tld: bool = False
    shortener: bool = False
    url_words: list[str] = []
    official_brand: str | None = None
    lookalike: Lookalike | None = None
    tranco_rank: int | None = None


def shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    return -sum(c / len(text) * math.log2(c / len(text)) for c in counts.values())


def _decode_host(host: str) -> str:
    try:
        return host.encode("ascii").decode("idna")
    except (UnicodeError, ValueError):
        return host


def skeleton(text: str) -> str:
    return text.lower().translate(CONFUSABLES)


def find_lookalike(
    host: str, unicode_host: str, registered: str | None, label: str, subdomain: str
) -> Lookalike | None:
    """Does this name imitate a brand it doesn't belong to?"""
    if official_name(host, registered):
        return None
    uni_label = _decode_host(label)
    tokens = [t for t in re.split(r"[-_.0-9]+", label.lower()) if t]
    sub_labels = [s for s in subdomain.lower().split(".") if s]
    best: Lookalike | None = None
    for brand in brands():
        for blabel in brand.labels:
            if uni_label != label and skeleton(uni_label) == blabel:
                return Lookalike(
                    brand=brand.name,
                    category=brand.category,
                    kind="homograph",
                    detail=f'uses look-alike letters from another alphabet to spell "{blabel}"',
                )
            if label != blabel and skeleton(label) == blabel:
                return Lookalike(
                    brand=brand.name,
                    category=brand.category,
                    kind="typo",
                    detail=f'swaps letters for digits to spell "{blabel}"',
                )
            limit = 2 if len(blabel) >= 9 else 1 if len(blabel) >= 6 else 0
            if limit and label != blabel and DamerauLevenshtein.distance(label, blabel) <= limit:
                best = best or Lookalike(
                    brand=brand.name,
                    category=brand.category,
                    kind="typo",
                    detail=f'is one or two letters away from "{blabel}"',
                )
            elif label != blabel and (blabel in tokens or (len(blabel) >= 5 and blabel in label)):
                best = best or Lookalike(
                    brand=brand.name,
                    category=brand.category,
                    kind="combo",
                    detail=f'adds extra words around "{blabel}"',
                )
            elif blabel in sub_labels or any(s.startswith(blabel + "-") for s in sub_labels):
                best = best or Lookalike(
                    brand=brand.name,
                    category=brand.category,
                    kind="subdomain",
                    detail=f'puts "{blabel}" in front of an unrelated domain',
                )
    return best


def analyze_link(url: str) -> LinkFeatures:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().rstrip(".")
    try:
        port = parts.port
    except ValueError:
        port = None
    features = LinkFeatures(
        url=url, host=host, length=len(url), port=port if port not in (None, 80, 443) else None
    )
    features.has_at = "@" in (parts.netloc or "")
    features.double_slash_path = "//" in (parts.path or "")[1:]
    path_words = set(re.split(r"[^a-z0-9-]+", (parts.path + " " + parts.query).lower()))
    host_words = set(re.split(r"[^a-z0-9-]+|-", host))
    features.url_words = sorted((path_words | host_words) & URL_WORDS)

    try:
        ipaddress.ip_address(host.strip("[]"))
        features.is_ip = True
        return features
    except ValueError:
        pass

    if "xn--" in host:
        features.unicode_host = _decode_host(host)
    pub = _public(host)
    site = _sites(host)
    features.registered_domain = pub.top_domain_under_public_suffix or None
    features.site = site.top_domain_under_public_suffix or None
    features.suffix = pub.suffix or None
    features.free_hosting = site.suffix if site.is_private and site.suffix else None
    features.subdomain_depth = len([s for s in site.subdomain.split(".") if s])
    label = pub.domain or ""
    features.digit_ratio = round(sum(c.isdigit() for c in host) / max(len(host), 1), 2)
    features.hyphens = label.count("-")
    features.entropy = round(shannon_entropy(label), 2)
    features.abused_tld = (pub.suffix or "").split(".")[-1] in ABUSED_TLDS
    features.shortener = features.registered_domain in SHORTENERS
    features.tranco_rank = toplist.rank(features.site)

    official = official_name(host, features.registered_domain)
    features.official_brand = official
    # A popular site isn't a lookalike, even if its name contains a brand (icicidirect.com, hdfclife.com).
    if not official and features.tranco_rank is None:
        features.lookalike = find_lookalike(
            host, features.unicode_host or host, features.registered_domain, label, pub.subdomain
        )
    return features


def brand_by_name(name: str | None) -> Brand | None:
    return next((b for b in brands() if b.name == name), None) if name else None

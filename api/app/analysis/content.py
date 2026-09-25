"""Clues in the page itself. The HTML is only read here, on the server, as plain data.
It is never shown to anyone and never treated as instructions (safety rules 5 and 6)."""

import re
from urllib.parse import urljoin, urlsplit

import tldextract
from bs4 import BeautifulSoup
from pydantic import BaseModel

from app.analysis.brands import brands

MAX_HTML = 2_000_000
_public = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

# What a form field asks for, judged from its name, id, placeholder, label, and so on.
SENSITIVE = {
    "password": r"pass(word|wd|code)?\b|pwd|\bpin\b(?!code)",
    "card": r"card.?(no|num)|cc.?(num|no)|credit.?card|debit.?card|card.?holder",
    "cvv": r"\bcvv2?\b|\bcvc\b|\bcsc\b|security.?code",
    "expiry": r"expir|valid.?(thru|till|upto)|\bmm.?/?.?yy\b",
    "otp": r"\botp\b|one.?time.?(pass|code)|verification.?code|sms.?code",
    "upi_pin": r"upi.?pin|\bmpin\b",
    "atm_pin": r"atm.?pin|card.?pin",
    "aadhaar": r"aadh?aa?r|\buidai\b",
    "pan": r"\bpan\b.?(card|no|number)?|permanent.?account",
    "bank_account": r"account.?(no|num)|a/c.?no|\bifsc\b",
    "netbanking": r"net.?banking|internet.?banking|customer.?id|\bcif\b",
    "seed_phrase": r"seed|mnemonic|recovery.?phrase|secret.?phrase|private.?key|12.?words|24.?words",
    "ssn": r"\bssn\b|social.?security",
}
SENSITIVE_RE = {k: re.compile(v, re.I) for k, v in SENSITIVE.items()}

PHRASES = {
    "urgency": [
        r"(account|card|kyc).{0,40}(suspend|block|expir|clos|lock|deactivat)",
        r"within 24 hours",
        r"immediately",
        r"unusual activity",
        r"confirm your identity",
        r"update your kyc",
        r"kyc (update|pending|expired)",
        r"last warning",
        r"final notice",
    ],
    "prize": [
        r"congratulations",
        r"you('ve| have)? won",
        r"\bwinner\b",
        r"lottery",
        r"lucky draw",
        r"claim (your )?(prize|reward|gift)",
        r"free gift",
        r"spin (the|to) win",
        r"scratch card",
    ],
    "job": [
        r"work from home",
        r"part[- ]?time",
        r"daily (income|earning|salary|payout)",
        r"earn (up to )?(₹|rs\.?|inr|\$)",
        r"per day",
        r"simple tasks?",
        r"like and earn",
        r"review and earn",
        r"telegram",
        r"investment plan",
        r"guaranteed returns?",
    ],
    "tech_support": [
        r"virus",
        r"infected",
        r"malware detected",
        r"trojan",
        r"call (microsoft|apple|windows|technical) support",
        r"toll[- ]?free",
        r"your (computer|pc|device) (is|has been) (locked|blocked|infected)",
        r"do not (restart|shut ?down|close)",
        r"error code",
    ],
    "government": [
        r"e-?challan",
        r"traffic (violation|fine|challan)",
        r"tax refund",
        r"customs (duty|clearance|fee)",
        r"parcel.{0,20}(on hold|held|pending)",
        r"delivery (failed|attempt)",
        r"update your (address|delivery)",
        r"pending challan",
        r"aadhaar.{0,20}(update|link|suspend)",
        r"pan.{0,20}(update|link|block)",
    ],
    "shopping": [
        r"add to cart",
        r"checkout",
        r"buy now",
        r"\d{2}% off",
        r"limited stock",
        r"flash sale",
        r"cash on delivery",
        r"free shipping",
        r"order now",
    ],
    "crypto": [
        r"connect (your )?wallet",
        r"airdrop",
        r"seed phrase",
        r"recovery phrase",
        r"wallet (validation|sync|verif|rectif)",
        r"claim (tokens|airdrop|rewards)",
        r"usdt",
        r"bitcoin",
        r"ethereum",
        r"\bnft\b",
    ],
    "download": [
        r"download (now|the app|update|apk)",
        r"install (the )?(update|app|plugin)",
        r"flash player",
        r"missing (codec|plugin)",
        r"update your browser",
        r"\.apk\b",
    ],
}
PHRASES_RE = {k: re.compile("|".join(v), re.I) for k, v in PHRASES.items()}

WALLETS = {
    "Bitcoin": re.compile(r"\b(bc1[ac-hj-np-z02-9]{25,60}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b"),
    "Ethereum": re.compile(r"\b0x[a-fA-F0-9]{40}\b"),
    "Tron": re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b"),
}
EXECUTABLE = re.compile(r"\.(exe|msi|scr|bat|cmd|ps1|vbs|jar|apk|dmg|pkg|iso)(\?|$)", re.I)
PHONE = re.compile(r"(\+?\d[\d\s().-]{8,}\d)")
OBFUSCATION = re.compile(r"\beval\s*\(|\batob\s*\(|\bunescape\s*\(|String\.fromCharCode|document\.write\s*\(")
RIGHT_CLICK = re.compile(
    r"oncontextmenu\s*=\s*[\"']?\s*return\s+false|contextmenu[\"']?\s*,\s*function|event\.button\s*==\s*2",
    re.I,
)
BASE64_BLOB = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")


class PageFeatures(BaseModel):
    captured: bool = False
    title: str | None = None
    forms: int = 0
    inputs: int = 0
    asks_for: list[str] = []  # keys of SENSITIVE
    form_targets: list[str] = []  # other domains that forms send data to
    form_to_other_domain: bool = False
    form_without_target: bool = False
    mailto_form: bool = False
    brands_mentioned: list[str] = []
    brand_in_title: list[str] = []
    wallets: list[str] = []
    phrases: dict[str, list[str]] = {}
    iframes: int = 0
    hidden_iframes: int = 0
    right_click_blocked: bool = False
    obfuscation: int = 0
    base64_share: float = 0.0
    links: int = 0
    empty_link_share: float = 0.0
    external_link_share: float = 0.0
    executable_links: list[str] = []
    phone_numbers: int = 0


def _registered(url: str) -> str | None:
    host = urlsplit(url).hostname or ""
    return _public(host).top_domain_under_public_suffix or host or None


def _field_text(field, soup: BeautifulSoup) -> str:
    bits = [
        field.get(a, "") for a in ("name", "id", "placeholder", "aria-label", "autocomplete", "title", "type")
    ]
    if field.get("id"):
        label = soup.find("label", attrs={"for": field["id"]})
        if label:
            bits.append(label.get_text(" ", strip=True))
    parent_label = field.find_parent("label")
    if parent_label:
        bits.append(parent_label.get_text(" ", strip=True))
    return " ".join(str(b) for b in bits if b)[:500]


def analyze_page(html: str | None, page_url: str | None) -> PageFeatures:
    if not html or not page_url:
        return PageFeatures()
    html = html[:MAX_HTML]
    soup = BeautifulSoup(html, "lxml")
    page_domain = _registered(page_url)
    f = PageFeatures(captured=True)
    f.title = (soup.title.get_text(" ", strip=True)[:200] if soup.title else None) or None

    # Forms and the fields in them.
    asks: set[str] = set()
    fields = soup.find_all(["input", "select", "textarea"])
    f.inputs = len(fields)
    for field in fields:
        kind = (field.get("type") or "").lower()
        if kind in ("hidden", "submit", "button", "image", "reset", "checkbox", "radio"):
            continue
        text = _field_text(field, soup)
        if kind == "password":
            asks.add("password")
        for key, pattern in SENSITIVE_RE.items():
            if pattern.search(text):
                asks.add(key)
    f.asks_for = sorted(asks)

    forms = soup.find_all("form")
    f.forms = len(forms)
    targets: set[str] = set()
    for form in forms:
        action = (form.get("action") or "").strip()
        if action.lower().startswith("mailto:"):
            f.mailto_form = True
        elif not action or action in ("#", "about:blank") or action.lower().startswith("javascript:"):
            if form.find("input"):
                f.form_without_target = True
        else:
            target = _registered(urljoin(page_url, action))
            if target and page_domain and target != page_domain:
                targets.add(target)
    f.form_targets = sorted(targets)
    f.form_to_other_domain = bool(targets)

    # Words on the page (visible text, the title, and image descriptions).
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.extract()
    text = soup.get_text(" ", strip=True)[:100_000]
    alts = " ".join(img.get("alt", "") for img in soup.find_all("img"))[:5000]
    words = f"{f.title or ''} {text} {alts}"
    mentioned = []
    in_title = []
    for brand in brands():
        if brand.mentioned_in(words):
            mentioned.append(brand.name)
            if f.title and brand.mentioned_in(f.title):
                in_title.append(brand.name)
    f.brands_mentioned = mentioned
    f.brand_in_title = in_title
    f.phrases = {
        k: sorted({m.group(0).lower() for m in p.finditer(words)})[:5] for k, p in PHRASES_RE.items()
    }
    f.phrases = {k: v for k, v in f.phrases.items() if v}
    f.wallets = sorted({name for name, p in WALLETS.items() if p.search(text)})
    f.phone_numbers = len({m.group(1) for m in PHONE.finditer(text)})

    # Structure and tricks (these use the raw HTML, including scripts).
    iframes = soup.find_all("iframe") if soup else []
    f.iframes = len(iframes)
    f.hidden_iframes = sum(
        1
        for i in iframes
        if i.get("width") in ("0", "1")
        or i.get("height") in ("0", "1")
        or "display:none" in (i.get("style") or "").replace(" ", "")
    )
    f.right_click_blocked = bool(RIGHT_CLICK.search(html))
    f.obfuscation = len(OBFUSCATION.findall(html))
    f.base64_share = round(sum(len(m) for m in BASE64_BLOB.findall(html)) / max(len(html), 1), 3)

    anchors = soup.find_all("a")
    f.links = len(anchors)
    if anchors:
        empty = external = 0
        for a in anchors:
            href = (a.get("href") or "").strip()
            if not href or href == "#" or href.lower().startswith("javascript:"):
                empty += 1
            elif href.lower().startswith(("http://", "https://", "//")):
                target = _registered(urljoin(page_url, href))
                if target and page_domain and target != page_domain:
                    external += 1
            if EXECUTABLE.search(href):
                f.executable_links.append(href.rsplit("/", 1)[-1][:80])
        f.empty_link_share = round(empty / len(anchors), 2)
        f.external_link_share = round(external / len(anchors), 2)
    f.executable_links = sorted(set(f.executable_links))[:10]
    return f

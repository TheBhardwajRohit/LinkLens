"""What kind of scam is this? Simple rules over the clues found, scored per type.
The best-scoring type wins if it has enough evidence."""

from app.analysis.brands import Brand, brands
from app.analysis.content import PageFeatures
from app.analysis.lexical import LinkFeatures
from app.analysis.models import ScamType

LABELS = {
    "banking": "Banking or payment fraud",
    "credentials": "Fake login (password theft)",
    "crypto": "Crypto scam",
    "prize": "Fake prize or lottery",
    "shop": "Fake online shop",
    "tech_support": "Tech support scam",
    "malware": "Malware download",
    "job": "Job or task scam",
    "government": "Government impersonation",
}
MIN_EVIDENCE = 3

FIELD_WORDS = {
    "password": "a password or PIN",
    "card": "a card number",
    "cvv": "the card's CVV",
    "expiry": "the card's expiry date",
    "otp": "a one-time password (OTP)",
    "upi_pin": "a UPI PIN",
    "atm_pin": "an ATM PIN",
    "aadhaar": "an Aadhaar number",
    "pan": "a PAN number",
    "bank_account": "bank account details",
    "netbanking": "net banking login details",
    "seed_phrase": "a crypto wallet recovery phrase",
    "ssn": "a Social Security number",
}


def impersonated_brands(
    link: LinkFeatures, page: PageFeatures, page_host: str, page_domain: str | None
) -> list[Brand]:
    """Brands the link or page pretends to be, while not being that brand's real site.

    A plain mention isn't enough (real sites mention other brands all the time). It counts when the
    link imitates the brand, the page's title claims it, or the page names it while asking for
    passwords, card numbers, or similar."""
    by_name = {b.name: b for b in brands()}
    found: list[Brand] = []
    if link.lookalike and link.lookalike.brand in by_name:
        found.append(by_name[link.lookalike.brand])
    candidates = list(page.brand_in_title)
    if page.asks_for:
        candidates += page.brands_mentioned
    for name in candidates:
        brand = by_name.get(name)
        if brand and brand not in found and not brand.is_official(page_host, page_domain):
            found.append(brand)
    return found


def classify(
    link: LinkFeatures, page: PageFeatures, impersonated: list[Brand], downloads: bool
) -> ScamType | None:
    asks = set(page.asks_for)
    p = page.phrases
    cats = {b.category for b in impersonated}
    scores: dict[str, int] = dict.fromkeys(LABELS, 0)
    evidence: dict[str, list[str]] = {k: [] for k in LABELS}

    def add(kind: str, points: int, why: str) -> None:
        scores[kind] += points
        evidence[kind].append(why)

    if cats & {"bank", "payment"}:
        add("banking", 3, "pretends to be a bank or payment service")
    if asks & {"netbanking", "otp", "upi_pin", "atm_pin", "card", "cvv", "bank_account"}:
        add("banking", 2, "asks for banking or card details")
    if "urgency" in p and cats & {"bank", "payment"}:
        add("banking", 1, "pressures you to act quickly")

    if "password" in asks:
        add("credentials", 2, "asks for a password")
    if impersonated and not cats & {"bank", "payment", "crypto", "government"}:
        add("credentials", 2, f"pretends to be {impersonated[0].name}")
    if page.form_to_other_domain and "password" in asks:
        add("credentials", 1, "sends the login to a different website")

    if "seed_phrase" in asks:
        add("crypto", 4, "asks for your wallet recovery phrase")
    if page.wallets:
        add("crypto", 2, "shows crypto wallet addresses")
    if len(p.get("crypto", [])) >= 2:
        add("crypto", 2, "talks about wallets, airdrops, or tokens")
    if "crypto" in cats:
        add("crypto", 2, "pretends to be a crypto service")

    if len(p.get("prize", [])) >= 2:
        add("prize", 3, "says you've won something")
    elif p.get("prize"):
        add("prize", 1, "mentions prizes or gifts")
    if p.get("prize") and asks & {"card", "cvv", "bank_account", "upi_pin"}:
        add("prize", 1, "asks for payment details to claim it")

    if len(p.get("shopping", [])) >= 2:
        add("shop", 2, "looks like an online shop")
    if p.get("shopping") and asks & {"card", "cvv"}:
        add("shop", 1, "asks for card details at checkout")
    if "shopping" in cats:
        add("shop", 2, "pretends to be a well-known shop")

    if len(p.get("tech_support", [])) >= 2:
        add("tech_support", 3, "claims your device has a problem")
    if p.get("tech_support") and page.phone_numbers:
        add("tech_support", 1, "gives a phone number to call")

    if downloads:
        add("malware", 4, "tries to download a file")
    if page.executable_links:
        add("malware", 2, "links to program files")
    if p.get("download"):
        add("malware", 1, "pushes you to install something")

    if len(p.get("job", [])) >= 2:
        add("job", 3, "offers easy money for simple tasks")

    if "government" in cats:
        add("government", 3, "pretends to be a government service")
    if p.get("government"):
        add("government", 2, "mentions fines, refunds, or held parcels")
    if p.get("government") and asks & {"card", "cvv", "upi_pin", "bank_account", "aadhaar", "pan"}:
        add("government", 1, "asks for payment or ID details")

    kind, best = max(scores.items(), key=lambda kv: kv[1])
    if best < MIN_EVIDENCE:
        return None
    brand = next((b.name for b in impersonated), None)
    return ScamType(id=kind, label=LABELS[kind], brand=brand, evidence=evidence[kind])

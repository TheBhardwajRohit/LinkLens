"""Rule-based score (phase 9 adds a machine-learning model on top).

Every rule that fires becomes a reason in plain words, with its points. Positive points raise
the risk; good signs (an old domain, a very popular site, a brand's real site) lower it.
The total is clamped to 0..100: 0 to 30 is Safe, 31 to 69 Suspicious, 70 to 100 Dangerous.
"""

from datetime import UTC, datetime
from urllib.parse import urlsplit

from app.analysis.content import PageFeatures
from app.analysis.lexical import LinkFeatures
from app.analysis.models import Reason, ScamType, Verdict
from app.analysis.scamtype import FIELD_WORDS

SAFE_MAX = 30
SUSPICIOUS_MAX = 69

LOOKALIKE_POINTS = {"homograph": 45, "typo": 35, "subdomain": 30, "combo": 25}
FIELD_POINTS = {
    "seed_phrase": 40,
    "otp": 30,
    "upi_pin": 30,
    "atm_pin": 30,
    "card": 25,
    "cvv": 25,
    "expiry": 15,
    "aadhaar": 20,
    "pan": 20,
    "ssn": 20,
    "netbanking": 15,
    "bank_account": 15,
    "password": 10,
}
PHRASE_REASONS = {
    "urgency": (10, "It pressures you to act fast"),
    "prize": (10, "It says you've won something"),
    "job": (10, "It promises easy money for simple tasks"),
    "tech_support": (15, "It claims your device has a problem and needs support"),
    "government": (10, "It talks about fines, refunds, or held parcels"),
    "download": (8, "It pushes you to download or install something"),
}


def verdict_for(score: int) -> Verdict:
    if score <= SAFE_MAX:
        return "safe"
    return "suspicious" if score <= SUSPICIOUS_MAX else "dangerous"


def _days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return max((datetime.now(UTC) - t).days, 0)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def link_reasons(link: LinkFeatures, requested: bool) -> list[Reason]:
    r: list[Reason] = []
    add = lambda text, pts: r.append(Reason(text=text, points=pts, area="link"))  # noqa: E731
    if link.lookalike:
        la = link.lookalike
        add(f"The address {la.detail}, imitating {la.brand}.", LOOKALIKE_POINTS.get(la.kind, 25))
    if link.is_ip:
        add("The link uses a bare IP address instead of a name.", 20)
    if link.has_at:
        add("The link hides its real destination after an @ sign.", 15)
    if link.unicode_host and not (link.lookalike and link.lookalike.kind == "homograph"):
        add(f'The name uses special characters: it really reads "{link.unicode_host}".', 10)
    if link.free_hosting:
        add(
            f"The page sits on a free hosting service ({link.free_hosting}), where anyone can make a site.",
            10,
        )
    if link.abused_tld and not link.tranco_rank:
        add(f"It uses the .{(link.suffix or '').split('.')[-1]} ending, which scammers use often.", 8)
    if link.subdomain_depth >= 3:
        add("The address has many layers of subdomains.", 8)
    label = (link.registered_domain or "").split(".")[0]
    if link.entropy >= 3.6 and len(label) >= 12:
        add("The name looks randomly generated.", 8)
    if link.hyphens >= 2:
        add("The name has several hyphens, like many scam domains.", 5)
    if link.url_words and not link.official_brand and not link.tranco_rank:
        add(
            f"The link uses words scammers like: {', '.join(link.url_words[:4])}.",
            min(4 * len(link.url_words), 12),
        )
    if link.length > 100:
        add("The link is unusually long.", 5)
    if link.port:
        add(f"The link uses an unusual port ({link.port}).", 8)
    if link.double_slash_path:
        add("The link has a hidden second address inside it.", 5)
    if requested and link.shortener:
        add("The link was shortened, which hides where it really goes.", 5)
    return r


def page_reasons(
    page: PageFeatures, impersonated: list[str], page_url: str | None, official: bool
) -> list[Reason]:
    r: list[Reason] = []
    add = lambda text, pts: r.append(Reason(text=text, points=pts, area="page"))  # noqa: E731
    if not page.captured:
        return r
    asks = [a for a in page.asks_for if a in FIELD_POINTS]
    if asks and not official:
        asks.sort(key=lambda a: -FIELD_POINTS[a])
        pts = min(FIELD_POINTS[asks[0]] + 5 * (len(asks) - 1), 45)
        words = [FIELD_WORDS[a] for a in asks[:4]]
        listed = ", ".join(words[:-1]) + " and " + words[-1] if len(words) > 1 else words[0]
        add(f"The page asks for {listed}.", pts)
        if page_url and page_url.startswith("http:"):
            add("It asks for private details without an encrypted (HTTPS) connection.", 20)
    if impersonated:
        brand = impersonated[0]
        if asks:
            add(f"It shows {brand}'s name but isn't {brand}'s real website.", 25)
        elif brand in page.brand_in_title:
            add(f"Its title says {brand}, but this isn't {brand}'s real website.", 10)
    if page.form_to_other_domain:
        add(f"Its form sends what you type to a different website ({', '.join(page.form_targets[:2])}).", 15)
    if page.form_without_target and asks:
        add("Its form sends your details through hidden code.", 5)
    if page.mailto_form:
        add("Its form emails what you type to someone.", 10)
    if page.wallets:
        add(f"It shows crypto wallet addresses ({', '.join(page.wallets)}).", 10)
    for key, (pts, text) in PHRASE_REASONS.items():
        found = page.phrases.get(key)
        if found and not (official and key in ("urgency", "government")):
            add(f'{text} ("{found[0]}").', pts)
    if page.executable_links:
        add(f"It links to program files ({', '.join(page.executable_links[:2])}).", 15)
    if page.right_click_blocked:
        add("It blocks right-clicking, to stop you from inspecting it.", 8)
    if page.obfuscation >= 3:
        add("Its code is scrambled to hide what it does.", 8)
    if page.hidden_iframes:
        add("It loads hidden frames.", 5)
    if page.links >= 5 and page.empty_link_share > 0.5:
        add("Most of its links go nowhere, a sign of a copied page.", 8)
    if page.base64_share > 0.3:
        add("Much of the page is packed into encoded blobs.", 5)
    return r


def behavior_reasons(visit: dict) -> list[Reason]:
    r: list[Reason] = []
    add = lambda text, pts: r.append(Reason(text=text, points=pts, area="behavior"))  # noqa: E731
    hops = visit.get("hops") or []
    if visit.get("stopped") == "blocked":
        add("The link tried to reach a private or internal address. Real websites never do that.", 25)
    if visit.get("downloads") or visit.get("stopped") == "download":
        add("The link tries to download a file onto your device.", 30)
    hosts = []
    for hop in hops:
        h = (urlsplit(hop.get("url", "")).hostname or "").lower()
        if h and (not hosts or hosts[-1] != h):
            hosts.append(h)
    if len(hosts) >= 3:
        add(f"The link bounces through {_plural(len(hosts), 'different site')} before landing.", 5)
    if any(h.get("kind") in ("meta", "script", "form") for h in hops[1:]):
        add("The page uses a hidden redirect to send you somewhere else.", 5)
    if visit.get("bot_check"):
        add(f"The page hides behind a bot check ({visit['bot_check']}).", 3)
    if visit.get("popups"):
        add("The page tried to open popup windows.", 3)
    return r


def domain_reasons(recon: dict) -> tuple[list[Reason], list[Reason]]:
    risks: list[Reason] = []
    good: list[Reason] = []
    reg = recon.get("registration") or {}
    age = reg.get("age_days")
    if reg.get("status") == "ok" and age is not None:
        if age < 7:
            risks.append(
                Reason(text=f"The domain is only {_plural(age, 'day')} old.", points=25, area="domain")
            )
        elif age < 30:
            risks.append(
                Reason(text=f"The domain is only {_plural(age, 'day')} old.", points=15, area="domain")
            )
        elif age < 180:
            risks.append(
                Reason(text=f"The domain is fairly new ({age // 30} months old).", points=5, area="domain")
            )
        elif age >= 3650:
            good.append(
                Reason(text=f"The domain has existed for {age // 365} years.", points=-15, area="domain")
            )
        elif age >= 1825:
            good.append(
                Reason(text=f"The domain has existed for {age // 365} years.", points=-10, area="domain")
            )
    elif reg.get("status") == "not_found":
        risks.append(Reason(text="The domain's registry has no record of it.", points=10, area="domain"))
    flags = " ".join(reg.get("flags") or []).lower()
    if any(w in flags for w in ("hold", "suspend")):
        risks.append(
            Reason(
                text="The registry has put the domain on hold, often because of abuse reports.",
                points=15,
                area="domain",
            )
        )
    dns = recon.get("dns") or {}
    if dns.get("status") == "not_found":
        risks.append(
            Reason(
                text="The domain no longer exists in DNS, typical of a scam site that was taken down.",
                points=5,
                area="domain",
            )
        )

    cert = recon.get("certificate") or {}
    if cert and not cert.get("trusted"):
        risks.append(
            Reason(
                text="Its security certificate isn't trusted: "
                + (cert.get("problem") or "browsers would warn."),
                points=15,
                area="certificate",
            )
        )
    history = recon.get("cert_history") or {}
    first = _days_since(history.get("first_seen"))
    if history.get("source") == "crt.sh" and first is not None and first < 7:
        risks.append(
            Reason(
                text=f"Its first security certificate was issued only {_plural(first, 'day')} ago.",
                points=8,
                area="certificate",
            )
        )
    return risks, good


def reputation_reasons(final: LinkFeatures, impersonated: list[str]) -> list[Reason]:
    good: list[Reason] = []
    if final.official_brand and not final.lookalike:
        good.append(
            Reason(text=f"This is the real website of {final.official_brand}.", points=-40, area="reputation")
        )
    if final.tranco_rank and not impersonated:
        if final.tranco_rank <= 10_000:
            good.append(
                Reason(
                    text=f"It's one of the world's most visited sites (#{final.tranco_rank:,} on Tranco).",
                    points=-30,
                    area="reputation",
                )
            )
        else:
            good.append(
                Reason(
                    text=f"It's a well-known site (#{final.tranco_rank:,} on the Tranco list).",
                    points=-15,
                    area="reputation",
                )
            )
    return good


PHRASE_BY_TYPE = {
    "banking": "banking page",
    "credentials": "login page",
    "crypto": "crypto wallet page",
    "prize": "prize or lottery scam",
    "shop": "online shop",
    "tech_support": "tech support page",
    "malware": "download that may be malware",
    "job": "job or task offer",
    "government": "government notice",
}
GENERIC_BY_TYPE = {
    "banking": "This looks like a fake banking page that steals account details.",
    "credentials": "This looks like a fake login page that steals passwords.",
    "crypto": "This looks like a crypto scam that tries to take your wallet.",
    "prize": "This looks like a fake prize or lottery scam.",
    "shop": "This looks like a fake online shop.",
    "tech_support": "This looks like a tech support scam.",
    "malware": "This link tries to get you to download something that may be malware.",
    "job": "This looks like a job or task scam.",
    "government": "This looks like a fake government notice.",
}


def summarize(
    verdict: Verdict, scam: ScamType | None, final: LinkFeatures, visit: dict, partial: bool
) -> str:
    if visit.get("stopped") == "blocked":
        return "This link leads to a private address, which real websites never do. Don't trust it."
    if verdict != "safe" and scam:
        if scam.brand and scam.id in PHRASE_BY_TYPE:
            article = "an" if PHRASE_BY_TYPE[scam.id][0] in "aeiou" else "a"
            kind = PHRASE_BY_TYPE[scam.id]
            if scam.id in ("prize", "job", "malware", "tech_support"):
                return f"This looks like {article} {kind} using {scam.brand}'s name."
            return f"This looks like a fake {scam.brand} {kind}."
        return GENERIC_BY_TYPE.get(scam.id, "This link shows several warning signs.")
    if verdict == "dangerous":
        return "Several strong warning signs. Treat this link as dangerous."
    if verdict == "suspicious":
        return "Some warning signs. Be careful with this link." + (
            " The page itself couldn't be checked." if partial else ""
        )
    if final.official_brand:
        return f"This looks like the real website of {final.official_brand}. No warning signs found."
    if final.tranco_rank:
        return "A well-known site with no warning signs found."
    if partial:
        return "No warning signs in the link, but the page itself couldn't be checked."
    return "No warning signs found. That doesn't guarantee it's safe, so stay careful."

"""Analysis: turn everything the scan found into a score, a verdict, a scam type, and reasons."""

from app.analysis import score as rules
from app.analysis.content import PageFeatures, analyze_page
from app.analysis.lexical import LinkFeatures, analyze_link
from app.analysis.models import Analysis, ScamType
from app.analysis.scamtype import LABELS, classify, impersonated_brands
from app.analysis.toplist import toplist
from app.fingerprint import Fingerprints
from app.ml import model as page_model

NOT_CAPTURED = ("blocked", "unreachable", "download", "crashed", "error")


def _lists_malware(blacklists: dict | None) -> bool:
    return any(
        s.get("status") == "listed" and "malware" in (s.get("threats") or [])
        for s in (blacklists or {}).get("sources") or []
    )


def is_trusted(final: LinkFeatures) -> bool:
    """A brand's real site, or one of the 10,000 most visited sites. Scam kits copy these, so they
    "match" their own copies: the scam families, the link graph, and the model never mark them down."""
    official = bool(final.official_brand) and not final.lookalike
    return official or (final.tranco_rank is not None and final.tranco_rank <= 10_000)


BOT_SCREEN_WORDS = 50


def is_bot_screen(bot_check: str | None, page: PageFeatures, words: int | None) -> bool:
    """True when all the sandbox saw was a bot-check screen ("Verifying you are human..."): a bot
    check was detected, there is nothing to fill in, and there is almost no text. That screen is
    not the page behind it, so the model has nothing to read. A page that merely carries a CAPTCHA
    next to its login form is a real page and doesn't count."""
    return (
        bool(bot_check)
        and page.captured
        and page.inputs == 0
        and words is not None
        and words < BOT_SCREEN_WORDS
    )


def _clamp(points: int) -> int:
    return max(0, min(100, points))


def analyze(
    visit: dict,
    recon: dict,
    requested_url: str,
    blacklists: dict | None = None,
    family: dict | None = None,
    siblings: dict | None = None,
    graph: dict | None = None,
    prints: Fingerprints | None = None,
) -> Analysis:
    """Read the link and the page, then judge them."""
    link = analyze_link(requested_url)
    final_url = visit.get("final_url") or requested_url
    final = analyze_link(final_url) if final_url != requested_url else link
    page = analyze_page(visit.get("html"), visit.get("final_url"))
    # The trained model reads the same link and page. It only speaks when a real page was captured.
    unread = is_bot_screen(visit.get("bot_check"), page, prints.words if prints else None)
    prediction = None
    if page.captured and not unread:
        # Imported here, not at the top: the feature code imports this package.
        from app.ml.features import vector

        copied = impersonated_brands(final, page, final.host, final.registered_domain)
        prediction = page_model.predict(vector(final, page, prints, len(copied)))
    return judge(link, final, page, visit, recon, blacklists, family, siblings, graph, prediction, unread)


def judge(
    link: LinkFeatures,
    final: LinkFeatures,
    page: PageFeatures,
    visit: dict,
    recon: dict,
    blacklists: dict | None = None,
    family: dict | None = None,
    siblings: dict | None = None,
    graph: dict | None = None,
    prediction: page_model.Prediction | None = None,
    unread: bool = False,
) -> Analysis:
    """Score what was already read. Split from `analyze` so the data jobs can score a dataset page
    without parsing it twice. `unread` says the sandbox only saw a bot-check screen, so the result
    is marked partial."""
    page_domain = final.registered_domain
    impersonated = impersonated_brands(final, page, final.host, page_domain)
    if link is not final and link.lookalike:
        impersonated = impersonated_brands(link, page, final.host, page_domain) or impersonated
    names = [b.name for b in impersonated]
    official = bool(final.official_brand) and not final.lookalike
    downloads = bool(visit.get("downloads")) or visit.get("stopped") == "download"

    reasons = rules.link_reasons(link, requested=True)
    if final is not link:
        seen = {r.text for r in reasons}
        reasons += [r for r in rules.link_reasons(final, requested=False) if r.text not in seen]
    reasons += rules.page_reasons(page, names, visit.get("final_url"), official)
    reasons += rules.behavior_reasons(visit)
    reasons += rules.blacklist_reasons(blacklists)
    trusted = is_trusted(final)
    reasons += rules.family_reasons(family, siblings, trusted)
    shared_host = final.free_hosting is not None
    domain_risks, good = rules.domain_reasons(recon, shared_host=shared_host)
    reasons += domain_risks
    graph_risks, graph_good = rules.graph_reasons(graph, trusted)
    reasons += graph_risks
    good += graph_good
    good += rules.reputation_reasons(final, names)
    # What the rules alone say. The model speaks last, and how much it may add depends on the
    # backing: the rule score without signs that honest and scam sites share (free hosting).
    credit = sum(r.points for r in good)
    rule_score = _clamp(sum(r.points for r in reasons) + credit)
    backing = _clamp(sum(r.points for r in reasons if r.backs_model) + credit)
    model_risks, model_good = rules.model_reasons(prediction, rule_score, backing, trusted, shared_host)
    reasons += model_risks
    good += model_good

    reasons.sort(key=lambda r: -r.points)
    good.sort(key=lambda r: r.points)
    total = _clamp(sum(r.points for r in reasons) + sum(r.points for r in good))
    if visit.get("stopped") == "blocked":
        # A link that leads to a private address is never a normal website, whatever else looks fine.
        total = max(total, rules.SAFE_MAX + 10)
    listing = max((r.points for r in reasons if r.area == "blacklist"), default=0)
    if listing >= rules.STRONG_LISTING:
        # Good signs elsewhere (an old domain, a tidy page) don't make a listed link safe to open.
        total = max(total, rules.SUSPICIOUS_MAX + 1)
    elif listing >= rules.LISTING:
        total = max(total, rules.SAFE_MAX + 1)
    verdict = rules.verdict_for(total)
    partial = visit.get("stopped") in NOT_CAPTURED or not page.captured or unread
    scam = classify(final, page, impersonated, downloads) if verdict != "safe" else None
    listed_by = list((blacklists or {}).get("listed_by") or [])
    if scam is None and verdict != "safe" and _lists_malware(blacklists):
        scam = ScamType(id="malware", label=LABELS["malware"], evidence=["a blacklist lists it as malware"])

    return Analysis(
        score=total,
        verdict=verdict,
        rule_score=rule_score,
        backing=backing,
        summary=rules.summarize(verdict, scam, final, visit, partial, listed_by, small_signs=bool(reasons)),
        scam_type=scam,
        reasons=reasons,
        good_signs=good,
        partial=partial,
        listed_by=listed_by,
        model=prediction,
        link=link,
        final_link=final if final is not link else None,
        page=page,
        tranco_list=toplist.list_id,
    )

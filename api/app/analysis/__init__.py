"""Analysis: turn everything the scan found into a score, a verdict, a scam type, and reasons."""

from app.analysis import score as rules
from app.analysis.content import PageFeatures, analyze_page
from app.analysis.lexical import LinkFeatures, analyze_link
from app.analysis.models import Analysis, ScamType
from app.analysis.scamtype import LABELS, classify, impersonated_brands
from app.analysis.toplist import toplist
from app.fingerprint import Fingerprints
from app.ml import model as page_model
from app.ml.features import vector

NOT_CAPTURED = ("blocked", "unreachable", "download", "crashed", "error")


def _lists_malware(blacklists: dict | None) -> bool:
    return any(
        s.get("status") == "listed" and "malware" in (s.get("threats") or [])
        for s in (blacklists or {}).get("sources") or []
    )


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
    # The trained model reads the same link and page. It only speaks when a page was captured.
    prediction = None
    if page.captured:
        copied = impersonated_brands(final, page, final.host, final.registered_domain)
        prediction = page_model.predict(vector(final, page, prints, len(copied)))
    return judge(link, final, page, visit, recon, blacklists, family, siblings, graph, prediction)


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
) -> Analysis:
    """Score what was already read. Split from `analyze` so the data jobs can score a dataset page
    without parsing it twice."""
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
    trusted = official or (final.tranco_rank is not None and final.tranco_rank <= 10_000)
    reasons += rules.family_reasons(family, siblings, trusted)
    domain_risks, good = rules.domain_reasons(recon)
    reasons += domain_risks
    graph_risks, graph_good = rules.graph_reasons(graph, trusted)
    reasons += graph_risks
    good += graph_good
    model_risks, model_good = rules.model_reasons(prediction, trusted)
    reasons += model_risks
    good += model_good
    good += rules.reputation_reasons(final, names)

    reasons.sort(key=lambda r: -r.points)
    good.sort(key=lambda r: r.points)
    total = max(0, min(100, sum(r.points for r in reasons) + sum(r.points for r in good)))
    if visit.get("stopped") == "blocked":
        # A link that leads to a private address is never a normal website, whatever else looks fine.
        total = max(total, rules.SAFE_MAX + 10)
    verdict = rules.verdict_for(total)
    partial = visit.get("stopped") in NOT_CAPTURED or not page.captured
    scam = classify(final, page, impersonated, downloads) if verdict != "safe" else None
    listed_by = list((blacklists or {}).get("listed_by") or [])
    if scam is None and verdict != "safe" and _lists_malware(blacklists):
        scam = ScamType(id="malware", label=LABELS["malware"], evidence=["a blacklist lists it as malware"])

    return Analysis(
        score=total,
        verdict=verdict,
        summary=rules.summarize(verdict, scam, final, visit, partial, listed_by),
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

"""Analysis: turn everything the scan found into a score, a verdict, a scam type, and reasons."""

from app.analysis import score as rules
from app.analysis.content import analyze_page
from app.analysis.lexical import analyze_link
from app.analysis.models import Analysis
from app.analysis.scamtype import classify, impersonated_brands
from app.analysis.toplist import toplist

NOT_CAPTURED = ("blocked", "unreachable", "download", "crashed", "error")


def analyze(visit: dict, recon: dict, requested_url: str) -> Analysis:
    link = analyze_link(requested_url)
    final_url = visit.get("final_url") or requested_url
    final = analyze_link(final_url) if final_url != requested_url else link

    page = analyze_page(visit.get("html"), visit.get("final_url"))
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
    domain_risks, good = rules.domain_reasons(recon)
    reasons += domain_risks
    good += rules.reputation_reasons(final, names)

    reasons.sort(key=lambda r: -r.points)
    good.sort(key=lambda r: r.points)
    total = max(0, min(100, sum(r.points for r in reasons) + sum(r.points for r in good)))
    verdict = rules.verdict_for(total)
    partial = visit.get("stopped") in NOT_CAPTURED or not page.captured
    scam = classify(final, page, impersonated, downloads) if verdict != "safe" else None

    return Analysis(
        score=total,
        verdict=verdict,
        summary=rules.summarize(verdict, scam, final, visit, partial),
        scam_type=scam,
        reasons=reasons,
        good_signs=good,
        partial=partial,
        link=link,
        final_link=final if final is not link else None,
        page=page,
        tranco_list=toplist.list_id,
    )

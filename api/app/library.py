"""One call that reads a page (link + HTML) into everything the page library and the model need.
Used by the data jobs, so dataset pages and feed pages are read exactly like scanned pages."""

from dataclasses import dataclass

from app.analysis.content import PageFeatures, analyze_page
from app.analysis.lexical import LinkFeatures, analyze_link
from app.analysis.models import ScamType
from app.analysis.scamtype import classify, impersonated_brands
from app.fingerprint import Fingerprints, html_fingerprints
from app.ml.features import vector


@dataclass
class Digest:
    link: LinkFeatures
    page: PageFeatures
    prints: Fingerprints
    impersonated: list[str]
    scam: ScamType | None
    features: list[float]


def digest_page(url: str, html: str | None, downloads: bool = False) -> Digest:
    link = analyze_link(url)
    page = analyze_page(html, url)
    prints = html_fingerprints(html, url)
    brands = impersonated_brands(link, page, link.host, link.registered_domain)
    scam = classify(link, page, brands, downloads)
    return Digest(
        link=link,
        page=page,
        prints=prints,
        impersonated=[b.name for b in brands],
        scam=scam,
        features=vector(link, page, prints, len(brands)),
    )

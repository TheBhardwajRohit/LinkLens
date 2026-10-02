"""Turns what the scan found into a fixed list of numbers a model can learn from.

Only things that can be read from the link and the page itself are used, because that's all the
training data has (research datasets hold a link and its HTML, not who registered the domain).
Popularity (Tranco rank) and "this is the brand's real site" are left out on purpose: the benign
half of the training data is mostly popular sites, so a model given those would just learn
"unpopular means scam". The rules still use them as good signs.
"""

import math
from urllib.parse import parse_qsl, urlsplit

from app.analysis.content import PHRASES, SENSITIVE, PageFeatures
from app.analysis.lexical import LinkFeatures
from app.fingerprint import Fingerprints

LOOKALIKE_KINDS = ("homograph", "typo", "combo", "subdomain")

NAMES: list[str] = (
    [
        "url_length",
        "host_length",
        "path_length",
        "query_length",
        "path_depth",
        "query_params",
        "host_dots",
        "https",
        "subdomain_depth",
        "digit_ratio",
        "hyphens",
        "entropy",
        "random_name",
        "is_ip",
        "has_at",
        "double_slash_path",
        "abused_tld",
        "shortener",
        "odd_port",
        "free_hosting",
        "punycode",
        "url_words",
        "lookalike",
    ]
    + [f"lookalike_{k}" for k in LOOKALIKE_KINDS]
    + [
        "captured",
        "forms",
        "inputs",
        "password_fields",
        "hidden_fields",
        "asks_count",
    ]
    + [f"asks_{k}" for k in SENSITIVE]
    + [
        "form_to_other_domain",
        "form_without_target",
        "mailto_form",
        "brands_mentioned",
        "brand_in_title",
        "impersonated",
        "wallets",
    ]
    + [f"phrases_{k}" for k in PHRASES]
    + [
        "iframes",
        "hidden_iframes",
        "right_click_blocked",
        "obfuscation",
        "base64_share",
        "links",
        "empty_link_share",
        "external_link_share",
        "executable_links",
        "phone_numbers",
        "scripts",
        "external_scripts",
        "images",
        "meta_refresh",
        "noindex",
        "has_title",
        "title_length",
        "tags_log",
        "words_log",
        "words_per_tag",
        "out_domains",
    ]
)


def vector(
    link: LinkFeatures, page: PageFeatures, prints: Fingerprints | None = None, impersonated: int = 0
) -> list[float]:
    """The numbers for one page, in the order of NAMES."""
    parts = urlsplit(link.url)
    path = parts.path or ""
    kind = link.lookalike.kind if link.lookalike else None
    tags = prints.tags if prints else 0
    words = prints.words if prints else 0
    f: dict[str, float] = {
        "url_length": link.length,
        "host_length": len(link.host),
        "path_length": len(path),
        "query_length": len(parts.query or ""),
        "path_depth": path.count("/"),
        "query_params": len(parse_qsl(parts.query or "", keep_blank_values=True)),
        "host_dots": link.host.count("."),
        "https": parts.scheme == "https",
        "subdomain_depth": link.subdomain_depth,
        "digit_ratio": link.digit_ratio,
        "hyphens": link.hyphens,
        "entropy": link.entropy,
        "random_name": link.random_name,
        "is_ip": link.is_ip,
        "has_at": link.has_at,
        "double_slash_path": link.double_slash_path,
        "abused_tld": link.abused_tld,
        "shortener": link.shortener,
        "odd_port": link.port is not None,
        "free_hosting": link.free_hosting is not None,
        "punycode": link.unicode_host is not None,
        "url_words": len(link.url_words),
        "lookalike": kind is not None,
        "captured": page.captured,
        "forms": page.forms,
        "inputs": page.inputs,
        "password_fields": page.password_fields,
        "hidden_fields": page.hidden_fields,
        "asks_count": len(page.asks_for),
        "form_to_other_domain": page.form_to_other_domain,
        "form_without_target": page.form_without_target,
        "mailto_form": page.mailto_form,
        "brands_mentioned": len(page.brands_mentioned),
        "brand_in_title": len(page.brand_in_title),
        "impersonated": impersonated,
        "wallets": len(page.wallets),
        "iframes": page.iframes,
        "hidden_iframes": page.hidden_iframes,
        "right_click_blocked": page.right_click_blocked,
        "obfuscation": page.obfuscation,
        "base64_share": page.base64_share,
        "links": page.links,
        "empty_link_share": page.empty_link_share,
        "external_link_share": page.external_link_share,
        "executable_links": len(page.executable_links),
        "phone_numbers": page.phone_numbers,
        "scripts": page.scripts,
        "external_scripts": page.external_scripts,
        "images": page.images,
        "meta_refresh": page.meta_refresh,
        "noindex": page.noindex,
        "has_title": page.title is not None,
        "title_length": len(page.title or ""),
        "tags_log": math.log1p(tags),
        "words_log": math.log1p(words),
        "words_per_tag": words / tags if tags else 0.0,
        "out_domains": len(prints.out_domains) if prints else 0,
    }
    for k in LOOKALIKE_KINDS:
        f[f"lookalike_{k}"] = kind == k
    for k in SENSITIVE:
        f[f"asks_{k}"] = k in page.asks_for
    for k in PHRASES:
        f[f"phrases_{k}"] = len(page.phrases.get(k, []))
    return [float(f[name]) for name in NAMES]

"""What the site's HTTP headers and HTML reveal about how it's built and hosted.
Works only on data the sandbox already captured; nothing is fetched here."""

import re

from app.recon.models import HttpInfo

SECURITY_HEADERS = {
    "strict-transport-security": "HSTS",
    "content-security-policy": "Content-Security-Policy",
    "x-frame-options": "X-Frame-Options",
    "x-content-type-options": "X-Content-Type-Options",
    "referrer-policy": "Referrer-Policy",
}

# (name, header to look for, text that header's value must contain; "" means any value)
HEADER_TECH = [
    ("Cloudflare", "cf-ray", ""),
    ("Cloudflare", "server", "cloudflare"),
    ("Vercel", "x-vercel-id", ""),
    ("Netlify", "x-nf-request-id", ""),
    ("Amazon CloudFront", "x-amz-cf-id", ""),
    ("Amazon S3", "server", "amazons3"),
    ("Fastly", "x-fastly-request-id", ""),
    ("Fastly", "x-served-by", "cache-"),
    ("GitHub Pages", "server", "github.com"),
    ("Google Cloud", "server", "google frontend"),
    ("Firebase Hosting", "x-firebase-hosting", ""),
    ("Shopify", "x-shopid", ""),
    ("Wix", "x-wix-request-id", ""),
    ("nginx", "server", "nginx"),
    ("Apache", "server", "apache"),
    ("LiteSpeed", "server", "litespeed"),
    ("Microsoft IIS", "server", "microsoft-iis"),
    ("PHP", "x-powered-by", "php"),
    ("Express", "x-powered-by", "express"),
    ("ASP.NET", "x-powered-by", "asp.net"),
    ("ASP.NET", "x-aspnet-version", ""),
    ("Next.js", "x-powered-by", "next.js"),
]

HTML_TECH = [
    ("WordPress", re.compile(r"/wp-content/|/wp-includes/", re.I)),
    ("Shopify", re.compile(r"cdn\.shopify\.com", re.I)),
    ("Wix", re.compile(r"static\.wixstatic\.com", re.I)),
    ("Squarespace", re.compile(r"static1\.squarespace\.com", re.I)),
    ("Weebly", re.compile(r"weebly\.com", re.I)),
    ("jQuery", re.compile(r"jquery(?:\.min)?\.js", re.I)),
]

_GENERATOR = re.compile(r"<meta[^>]+name=[\"']generator[\"'][^>]*content=[\"']([^\"']{1,80})", re.I)


def analyze(headers: dict[str, str] | None, html: str | None) -> HttpInfo:
    if not headers and not html:
        return HttpInfo(status="skipped")
    h = {k.lower(): v for k, v in (headers or {}).items()}
    tech: list[str] = []
    for name, header, needle in HEADER_TECH:
        value = h.get(header)
        if value is not None and needle in value.lower() and name not in tech:
            tech.append(name)
    page = (html or "")[:500_000]
    for name, pattern in HTML_TECH:
        if pattern.search(page) and name not in tech:
            tech.append(name)
    generator = _GENERATOR.search(page)
    return HttpInfo(
        server=h.get("server", "")[:120] or None,
        powered_by=h.get("x-powered-by", "")[:120] or None,
        generator=generator.group(1).strip() if generator else None,
        tech=tech,
        security_headers={label: key in h for key, label in SECURITY_HEADERS.items()},
    )

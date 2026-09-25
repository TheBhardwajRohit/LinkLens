"""Split a host name into its registered domain (paypal.co.uk from login.paypal.co.uk)."""

import ipaddress
from datetime import UTC, datetime

import tldextract

# Uses the Public Suffix List snapshot bundled with tldextract: no network, no cache files.
_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)


def is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def registered_domain(host: str) -> str | None:
    if not host or is_ip(host):
        return None
    return _extract(host.lower().rstrip(".")).top_domain_under_public_suffix or None


def parse_date(value: str | None) -> datetime | None:
    """Best effort for the many date formats registries use."""
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d-%b-%Y", "%Y.%m.%d", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                parsed = datetime.strptime(text.split(" (")[0].strip(), fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def age_days(created: datetime | None, now: datetime | None = None) -> int | None:
    if created is None:
        return None
    return max(((now or datetime.now(UTC)) - created).days, 0)

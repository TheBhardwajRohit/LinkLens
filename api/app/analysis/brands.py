"""The brand list, and helpers to tell a brand's real domains from lookalikes."""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).parent / "data" / "brands.json"

# Only real banks / government bodies can register names under these, so they're always official.
RESTRICTED_SUFFIXES = {"bank": (".bank.in",), "government": (".gov.in", ".nic.in", ".gov")}


@dataclass(frozen=True)
class Brand:
    name: str
    category: str
    domains: tuple[str, ...]
    labels: tuple[str, ...]
    patterns: tuple[re.Pattern, ...]

    def owns(self, host: str, registered: str | None) -> bool:
        """Is this one of the brand's own domains?"""
        host = host.lower().rstrip(".")
        for d in self.domains:
            if "." not in d:  # a brand's own top-level domain, like .sbi
                if host.endswith("." + d):
                    return True
            elif registered == d or host == d or host.endswith("." + d):
                return True
        return False

    def is_official(self, host: str, registered: str | None) -> bool:
        """Its own domain, or a restricted one only its kind of organization can register."""
        restricted = RESTRICTED_SUFFIXES.get(self.category, ())
        return self.owns(host, registered) or any(host.lower().endswith(s) for s in restricted)

    def mentioned_in(self, text: str) -> int:
        return sum(len(p.findall(text)) for p in self.patterns)


def _pattern(keyword: str) -> re.Pattern:
    if keyword.startswith("="):
        return re.compile(rf"(?<![\w]){re.escape(keyword[1:])}(?![\w])")
    return re.compile(rf"(?<![\w]){re.escape(keyword)}(?![\w])", re.I)


@lru_cache
def brands() -> tuple[Brand, ...]:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    return tuple(
        Brand(
            name=b["name"],
            category=b["category"],
            domains=tuple(d.lower() for d in b["domains"]),
            labels=tuple(label.lower() for label in b["labels"]),
            patterns=tuple(_pattern(k) for k in b["keywords"]),
        )
        for b in data["brands"]
    )


RESTRICTED_NAMES = {
    ".bank.in": "a registered Indian bank",
    ".gov.in": "Government of India",
    ".nic.in": "Government of India",
}


def official_brand(host: str, registered: str | None) -> Brand | None:
    """The brand whose real site this is, if any."""
    return next((b for b in brands() if b.owns(host, registered)), None)


def official_name(host: str, registered: str | None) -> str | None:
    """A brand's name, or who runs a restricted domain (only real banks can use .bank.in, and so on)."""
    brand = official_brand(host, registered)
    if brand:
        return brand.name
    return next((name for suffix, name in RESTRICTED_NAMES.items() if host.lower().endswith(suffix)), None)

"""How alike are two pages, judged from their fingerprints?

Each kind of fingerprint that agrees adds points. Two pages count as "the same design" only when
at least two different kinds agree and the points reach the threshold, so one lucky match (the same
default icon, say) is never enough. Used by the nightly family grouping and by live scans.
"""

import re
from typing import NamedTuple

import tlsh

MATCH_POINTS = 3.0
MIN_KINDS = 2
# Pages this small (an error message, an empty shell) look alike by accident.
MIN_TAGS = 15
MIN_WORDS = 20
# Agreement on what the page says or shows. Site builders (Wix, Google Sites, and the like) give
# thousands of unrelated pages the same code and structure, so those two alone prove nothing:
# at least one of these must agree as well.
CONTENT_KINDS = frozenset({"words", "look", "icon"})
# Standard notices that thousands of unrelated sites show: suspended, parked, blocked, not found.
BOILERPLATE_TITLE = re.compile(
    r"suspended|not found|\b40[34]\b|forbidden|access denied|domain (is )?for sale|parked|"
    r"just a moment|attention required|site can.t be reached|default web ?page|coming soon|"
    r"account (has been )?(disabled|terminated)|deceptive site|phishing (warning|detected)|"
    r"under construction|welcome to nginx|apache2? (ubuntu |debian )?default|index of /|"
    r"website (is )?(expired|unavailable)|bad gateway|service unavailable|default web ?site page|"
    r"resources and information|deceptive page|\b5\d\d: |web server is down|connection timed out|"
    r"error code \d|^error$|page not available",
    re.I,
)


class Prints(NamedTuple):
    """One page's fingerprints, with the 64-bit hashes as plain non-negative numbers."""

    tlsh: str | None = None
    dom_hash: str | None = None
    dom: int | None = None
    text: int | None = None
    phash: int | None = None
    favicon: int | None = None
    tags: int | None = None


class Likeness(NamedTuple):
    points: float
    kinds: tuple[str, ...]  # which fingerprints agreed: code, structure, words, look, icon
    percent: int  # a rough "how alike" figure for showing to people

    @property
    def match(self) -> bool:
        return (
            self.points >= MATCH_POINTS
            and len(self.kinds) >= MIN_KINDS
            and bool(CONTENT_KINDS.intersection(self.kinds))
        )


def boilerplate(title: str | None, words: int | None = None) -> bool:
    """Is this a standard notice or a nearly empty page? Such pages are the same on thousands of
    unrelated sites, so matching them would say nothing about who is behind a site."""
    if words is not None and words < MIN_WORDS:
        return True
    return bool(BOILERPLATE_TITLE.search(title or ""))


def unsigned(value: int | None) -> int | None:
    """Postgres stores 64-bit hashes signed; comparisons want them unsigned."""
    if value is None:
        return None
    return value + (1 << 64) if value < 0 else value


def from_hex(hex_hash: str | None) -> int | None:
    return int(hex_hash, 16) if hex_hash else None


def _bits(a: int | None, b: int | None) -> int | None:
    if a is None or b is None:
        return None
    return (a ^ b).bit_count()


def _code_distance(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    try:
        return tlsh.diff(a, b)
    except ValueError:
        return None


def compare(a: Prints, b: Prints, common_icons: frozenset[int] = frozenset()) -> Likeness:
    points = 0.0
    kinds: list[str] = []
    shares: list[float] = []

    code = _code_distance(a.tlsh, b.tlsh)
    if code is not None:
        shares.append(max(0.0, 1 - code / 300))
        gained = 2.5 if code <= 30 else 2.0 if code <= 60 else 1.0 if code <= 100 else 0.0
        if gained:
            points += gained
            kinds.append("code")

    structure = _bits(a.dom, b.dom)
    same_structure = a.dom_hash is not None and a.dom_hash == b.dom_hash
    if structure is not None or same_structure:
        shares.append(1.0 if same_structure else 1 - (structure or 0) / 64)
        gained = 1.5 if same_structure else 1.25 if structure <= 3 else 0.75 if structure <= 8 else 0.0
        if gained:
            points += gained
            kinds.append("structure")

    words = _bits(a.text, b.text)
    if words is not None:
        shares.append(1 - words / 64)
        gained = 2.0 if words <= 4 else 1.25 if words <= 8 else 0.5 if words <= 12 else 0.0
        if gained:
            points += gained
            kinds.append("words")

    look = _bits(a.phash, b.phash)
    if look is not None:
        shares.append(1 - look / 64)
        gained = 2.0 if look <= 4 else 1.25 if look <= 8 else 0.5 if look <= 10 else 0.0
        if gained:
            points += gained
            kinds.append("look")

    if a.favicon is not None and a.favicon == b.favicon and a.favicon not in common_icons:
        points += 1.0
        kinds.append("icon")

    # Tiny pages agree by accident, so they need every kind they have to agree strongly.
    small = min(a.tags or MIN_TAGS, b.tags or MIN_TAGS) < MIN_TAGS
    if small:
        points -= 1.5

    percent = round(100 * sum(shares) / len(shares)) if shares else 0
    return Likeness(points=round(points, 2), kinds=tuple(kinds), percent=percent)


KIND_WORDS = {
    "code": "nearly the same code",
    "structure": "the same page structure",
    "words": "nearly the same wording",
    "look": "the same look",
    "icon": "the same site icon",
}


def describe(kinds: tuple[str, ...] | list[str]) -> str:
    """ "nearly the same code, the same page structure and the same site icon" """
    words = [KIND_WORDS[k] for k in kinds if k in KIND_WORDS]
    if not words:
        return ""
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]

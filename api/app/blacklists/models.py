from typing import Literal

from pydantic import BaseModel

# listed          the source says this link (or its site) is bad
# clean           the source checked and has nothing on it (not proof that it's safe)
# unknown         the source has never seen it
# info            the source knows something worth showing, but it isn't a verdict
# not_configured  no key for this source
# quota           the free limit was reached
# timeout, error  the source didn't answer
# skipped         nothing to check, or the source's data isn't loaded yet
Status = Literal[
    "listed", "clean", "unknown", "info", "not_configured", "quota", "timeout", "error", "skipped"
]


class SourceResult(BaseModel):
    id: str  # "safe_browsing"
    name: str  # "Google Safe Browsing"
    status: Status = "unknown"
    note: str | None = None  # one plain sentence
    threats: list[str] = []  # plain words: "phishing", "malware"
    matched: list[str] = []  # which checked links matched (personal data already removed)
    detail: dict = {}  # small extras, such as how many vendors flagged it
    cached: bool = False
    reference: str | None = None  # where to read more (also the attribution link)


class Blacklists(BaseModel):
    sources: list[SourceResult] = []
    listed_by: list[str] = []  # names of the sources that list it
    checked: list[str] = []  # the links that were checked, personal data removed
    duration_ms: int = 0

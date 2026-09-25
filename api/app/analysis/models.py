from typing import Literal

from pydantic import BaseModel

from app.analysis.content import PageFeatures
from app.analysis.lexical import LinkFeatures

Verdict = Literal["safe", "suspicious", "dangerous"]


class Reason(BaseModel):
    text: str  # plain words, e.g. "The domain is only 3 days old"
    points: int  # positive raises the risk, negative lowers it
    area: Literal["link", "page", "domain", "certificate", "server", "behavior", "reputation"]


class ScamType(BaseModel):
    id: str
    label: str  # e.g. "Banking fraud"
    brand: str | None = None
    evidence: list[str] = []


class Analysis(BaseModel):
    score: int
    verdict: Verdict
    summary: str
    scam_type: ScamType | None = None
    reasons: list[Reason] = []  # raise the risk, strongest first
    good_signs: list[Reason] = []  # lower the risk
    partial: bool = False  # true when the page itself couldn't be checked
    link: LinkFeatures
    final_link: LinkFeatures | None = None
    page: PageFeatures
    tranco_list: str | None = None

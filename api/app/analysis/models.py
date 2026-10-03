from typing import Literal

from pydantic import BaseModel, Field

from app.analysis.content import PageFeatures
from app.analysis.lexical import LinkFeatures
from app.ml.model import Prediction

Verdict = Literal["safe", "suspicious", "dangerous"]


class Reason(BaseModel):
    text: str  # plain words, e.g. "The domain is only 3 days old"
    points: int  # positive raises the risk, negative lowers it
    area: Literal[
        "link",
        "page",
        "domain",
        "certificate",
        "server",
        "behavior",
        "reputation",
        "blacklist",
        "family",
        "graph",
        "model",
    ]
    # False for a sign that honest and scam sites share (being on a free hosting service). It still
    # adds its points, but it doesn't let the model count in full (see score.model_say).
    backs_model: bool = Field(default=True, exclude=True)


class ScamType(BaseModel):
    id: str
    label: str  # e.g. "Banking fraud"
    brand: str | None = None
    evidence: list[str] = []


class Analysis(BaseModel):
    score: int
    verdict: Verdict
    rule_score: int = 0  # what the rules alone scored, before the model spoke
    backing: int = 0  # the part of rule_score that lets the model count in full
    summary: str
    scam_type: ScamType | None = None
    reasons: list[Reason] = []  # raise the risk, strongest first
    good_signs: list[Reason] = []  # lower the risk
    partial: bool = False  # true when the page itself couldn't be checked
    listed_by: list[str] = []  # blacklists that list this link
    model: Prediction | None = None  # what the trained page-reading model thinks
    link: LinkFeatures
    final_link: LinkFeatures | None = None
    page: PageFeatures
    tranco_list: str | None = None

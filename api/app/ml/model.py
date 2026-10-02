"""The trained page-reading model, run in plain Python.

The model is a set of gradient-boosted decision trees trained with LightGBM (see jobs/train.py).
Training needs LightGBM; using the model doesn't. A tree is just a list of "is feature X at most
T? go left, else right" questions ending in a number, and the model's answer is the sum over all
trees, squashed to a 0..1 probability. Walking the trees here keeps LightGBM (and its system
libraries) out of the scan server.

Besides the probability, each prediction comes with "what pushed it": for every question on the
way down a tree, the change in the tree's expected answer is credited to the feature that was
asked about (the Saabas method). Summed over all trees, those credits add up exactly to the
model's raw output, so they are a faithful, if simple, explanation.
"""

import json
import math
import struct
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from app.ml.features import NAMES

MODEL_PATH = Path(__file__).parent / "model.json"

# How each feature is described to a person. Features missing here fall back to their name.
PLAIN = {
    "url_length": "the length of the link",
    "host_length": "the length of the site name",
    "path_length": "the length of the link's path",
    "query_length": "the extra data in the link",
    "path_depth": "how deep the link's path goes",
    "query_params": "the number of values in the link",
    "host_dots": "the number of dots in the site name",
    "https": "whether the link uses HTTPS",
    "subdomain_depth": "the layers of subdomains",
    "digit_ratio": "the share of digits in the site name",
    "hyphens": "the hyphens in the name",
    "entropy": "how random the name looks",
    "random_name": "a machine-made looking name",
    "is_ip": "a bare IP address instead of a name",
    "abused_tld": "a domain ending scammers use often",
    "free_hosting": "being on a free hosting service",
    "url_words": "scam-style words in the link",
    "lookalike": "a name that imitates a brand",
    "forms": "the forms on the page",
    "inputs": "the number of input fields",
    "password_fields": "the password fields",
    "hidden_fields": "the hidden form fields",
    "asks_count": "how many private details it asks for",
    "asks_password": "asking for a password",
    "asks_otp": "asking for a one-time password",
    "asks_card": "asking for a card number",
    "form_to_other_domain": "a form that sends data to another site",
    "form_without_target": "a form handled by hidden code",
    "brands_mentioned": "the brand names on the page",
    "brand_in_title": "a brand name in the title",
    "impersonated": "showing a brand's name on a site that isn't the brand's",
    "iframes": "the embedded frames",
    "obfuscation": "scrambled code",
    "base64_share": "the share of the page packed into encoded blobs",
    "links": "the number of links on the page",
    "empty_link_share": "the share of links that go nowhere",
    "external_link_share": "the share of links to other sites",
    "scripts": "the number of scripts",
    "external_scripts": "the scripts loaded from other sites",
    "images": "the number of images",
    "meta_refresh": "an automatic redirect tag",
    "noindex": "hiding from search engines",
    "has_title": "whether the page has a title",
    "title_length": "the length of the page title",
    "tags_log": "the size of the page",
    "words_log": "the amount of text",
    "words_per_tag": "how much text there is for the page's size",
    "out_domains": "the number of other sites it links to",
    "phone_numbers": "the phone numbers on the page",
}


def model_points(probability: float) -> int:
    """How many points the model's opinion adds to (or takes off) the risk score. The steps were
    chosen from the test-set results in docs/MODEL_REPORT.md: the higher the model's probability,
    the more often it is right, so the more it counts."""
    if probability >= 0.95:
        return 30
    if probability >= 0.8:
        return 22
    if probability >= 0.6:
        return 12
    if probability >= 0.4:
        return 5
    if probability <= 0.05:
        return -12
    if probability <= 0.15:
        return -6
    return 0


def as_float32(values: list[float]) -> list[float]:
    """Round each number the way the training data was stored (32-bit), so a value sitting right on
    a tree's threshold falls on the same side here as it did in training."""
    return list(struct.unpack(f"{len(values)}f", struct.pack(f"{len(values)}f", *values)))


class Factor(BaseModel):
    feature: str
    plain: str  # "asking for a one-time password"
    push: float  # positive pushes toward phishing, negative away from it


class Prediction(BaseModel):
    probability: float  # 0..1, the model's estimate that the page is phishing
    factors: list[Factor] = []  # the strongest pushes, both ways
    trained: str | None = None  # when the model was trained


class TreeModel:
    """Trees stored as flat lists. For node i of a tree: feature[i] < 0 means a leaf whose answer
    is value[i]; otherwise go to left[i] when x[feature[i]] <= threshold[i], else to right[i].
    value[i] of an inner node is the tree's expected answer at that point."""

    def __init__(self, data: dict):
        self.features: list[str] = data["features"]
        self.trees: list[dict] = data["trees"]
        self.base: float = data.get("base", 0.0)
        self.meta: dict = data.get("meta", {})
        if self.features != NAMES:
            raise ValueError("The model was trained on a different feature list than this code uses.")

    def raw(self, x: list[float]) -> tuple[float, list[float]]:
        """The model's raw output and each feature's share of it."""
        credit = [0.0] * len(x)
        total = self.base
        for tree in self.trees:
            feature, threshold = tree["f"], tree["t"]
            left, right, value = tree["l"], tree["r"], tree["v"]
            node = 0
            while feature[node] >= 0:
                child = left[node] if x[feature[node]] <= threshold[node] else right[node]
                credit[feature[node]] += value[child] - value[node]
                node = child
            total += value[node]
        return total, credit

    def predict(self, x: list[float], top: int = 4) -> Prediction:
        total, credit = self.raw(as_float32(x))
        probability = 1.0 / (1.0 + math.exp(-max(min(total, 30.0), -30.0)))
        ranked = sorted(range(len(credit)), key=lambda i: -abs(credit[i]))[:top]
        factors = [
            Factor(
                feature=NAMES[i],
                plain=PLAIN.get(NAMES[i], NAMES[i].replace("_", " ")),
                push=round(credit[i], 3),
            )
            for i in ranked
            if abs(credit[i]) >= 0.05
        ]
        return Prediction(
            probability=round(probability, 4), factors=factors, trained=self.meta.get("trained")
        )


@lru_cache
def load(path: Path = MODEL_PATH) -> TreeModel | None:
    """The model that ships with the code, or None when there is none (the rules then score alone)."""
    if not path.exists():
        return None
    try:
        return TreeModel(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, KeyError):
        return None


def predict(x: list[float]) -> Prediction | None:
    model = load()
    return model.predict(x) if model else None

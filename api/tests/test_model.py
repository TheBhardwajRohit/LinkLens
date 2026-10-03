"""The plain-Python model runner, checked on a tiny hand-made model, plus how the model's opinion
turns into points and words."""

import json

import pytest

from app.analysis.score import BACKING_MIN, MODEL_ALONE_MAX, SAFE_MAX, model_reasons, model_say
from app.ml import model as m
from app.ml.features import NAMES

OTP = NAMES.index("asks_otp")
HOST = NAMES.index("host_length")


def tiny_model() -> dict:
    """Two trees. Tree 1 asks "does the page ask for an OTP?". Tree 2 asks "is the site name long?",
    and if so, "does it ask for an OTP?"."""
    return {
        "features": NAMES,
        "base": 0.0,
        "meta": {"trained": "2026-10-03"},
        "trees": [
            # node 0: asks_otp <= 0.5 ? node 1 (leaf -1.0) : node 2 (leaf +2.0); expected value 0.2
            {"f": [OTP, -1, -1], "t": [0.5, 0, 0], "l": [1, -1, -1], "r": [2, -1, -1], "v": [0.2, -1.0, 2.0]},
            # node 0: host_length <= 60 ? leaf 1 (-0.5) : node 2; node 2: asks_otp <= 0.5 ? leaf 3 : leaf 4
            {
                "f": [HOST, -1, OTP, -1, -1],
                "t": [60.0, 0, 0.5, 0, 0],
                "l": [1, -1, 3, -1, -1],
                "r": [2, -1, 4, -1, -1],
                "v": [0.0, -0.5, 0.6, 0.1, 1.5],
            },
        ],
    }


def page(**values: float) -> list[float]:
    x = [0.0] * len(NAMES)
    for name, value in values.items():
        x[NAMES.index(name)] = value
    return x


def test_walking_the_trees_gives_the_sum_of_the_leaves():
    model = m.TreeModel(tiny_model())
    total, _ = model.raw(page(asks_otp=1, host_length=90))
    assert total == pytest.approx(2.0 + 1.5)
    total, _ = model.raw(page(asks_otp=0, host_length=20))
    assert total == pytest.approx(-1.0 - 0.5)
    total, _ = model.raw(page(asks_otp=0, host_length=60))  # exactly on the threshold goes left
    assert total == pytest.approx(-1.0 - 0.5)


def test_each_features_share_adds_up_to_the_answer():
    model = m.TreeModel(tiny_model())
    total, credit = model.raw(page(asks_otp=1, host_length=90))
    roots = 0.2 + 0.0  # what the trees expect before asking anything
    assert sum(credit) + roots == pytest.approx(total)
    assert credit[OTP] == pytest.approx((2.0 - 0.2) + (1.5 - 0.6))
    assert credit[HOST] == pytest.approx(0.6 - 0.0)


def test_prediction_is_a_probability_with_its_main_causes_in_plain_words():
    got = m.TreeModel(tiny_model()).predict(page(asks_otp=1, host_length=90))
    assert 0.96 < got.probability < 0.98  # 1 / (1 + e^-3.5)
    assert [f.feature for f in got.factors] == ["asks_otp", "host_length"]
    assert got.factors[0].plain == "asking for a one-time password" and got.factors[0].push > 0
    assert got.trained == "2026-10-03"
    calm = m.TreeModel(tiny_model()).predict(page())
    assert calm.probability < 0.2 and calm.factors[0].push < 0


def test_a_model_for_a_different_feature_list_is_refused(tmp_path):
    wrong = tiny_model() | {"features": NAMES[:-1]}
    with pytest.raises(ValueError):
        m.TreeModel(wrong)
    path = tmp_path / "model.json"
    path.write_text(json.dumps(wrong), encoding="utf-8")
    assert m.load(path) is None  # the scan then runs on the rules alone
    assert m.load(tmp_path / "missing.json") is None


def test_values_are_rounded_like_the_training_data():
    assert m.as_float32([0.1, 60.0, 1 / 3]) == pytest.approx([0.1, 60.0, 1 / 3], rel=1e-6)
    assert m.as_float32([0.1])[0] != 0.1  # 32-bit rounding really happened


def test_points_grow_with_the_models_confidence():
    assert [m.model_points(p) for p in (0.99, 0.85, 0.7, 0.45, 0.3, 0.1, 0.02)] == [
        50,
        40,
        25,
        10,
        0,
        -10,
        -20,
    ]


def test_the_models_opinion_becomes_a_reason():
    sure = m.Prediction(
        probability=0.97,
        factors=[
            m.Factor(feature="asks_otp", plain="asking for a one-time password", push=1.9),
            m.Factor(feature="links", plain="the number of links on the page", push=-0.4),
            m.Factor(
                feature="impersonated",
                plain="showing a brand's name on a site that isn't the brand's",
                push=0.8,
            ),
        ],
    )
    risks, good = model_reasons(sure, rule_score=40, backing=40, trusted=False)
    assert good == [] and risks[0].points == 50 and risks[0].area == "model"
    assert risks[0].text == (
        "The page-reading model rates this page 97% likely to be a scam page, mostly because of asking for a "
        "one-time password and showing a brand's name on a site that isn't the brand's."
    )
    # A brand's real site is never marked down by the model, but may still be marked up.
    assert model_reasons(sure, rule_score=40, backing=40, trusted=True) == ([], [])
    risks, good = model_reasons(m.Prediction(probability=0.03), rule_score=0, backing=0, trusted=True)
    assert risks == [] and good[0].points == -20
    assert good[0].text == "The page-reading model sees little that looks like a scam page (3%)."
    assert model_reasons(m.Prediction(probability=0.3), rule_score=40, backing=40, trusted=False) == ([], [])
    assert model_reasons(None, rule_score=40, backing=40, trusted=False) == ([], [])


def test_alone_the_model_cannot_lift_a_page_out_of_safe():
    assert MODEL_ALONE_MAX <= SAFE_MAX
    # The rules found nothing: however sure the model is, it adds no more than the limit.
    assert [model_say(p, 0, 0, False) for p in (0.99, 0.85, 0.7)] == [MODEL_ALONE_MAX] * 3
    assert model_say(0.99, BACKING_MIN - 1, BACKING_MIN - 1, False) == MODEL_ALONE_MAX
    # Small opinions and good opinions are not touched by the limit.
    assert model_say(0.45, 0, 0, False) == 10
    assert model_say(0.02, 0, 0, False) == -20
    # Rule points that are no backing (free hosting, plus a minor sign) leave less room: the page
    # still ends at the top of Safe, never above it.
    assert model_say(0.99, 10, 0, False) == 20 and 10 + 20 == SAFE_MAX
    assert model_say(0.99, 15, 5, False) == 15
    assert model_say(0.45, 27, 7, False) == 3
    assert all(r + model_say(0.99, r, min(r, BACKING_MIN - 1), False) <= SAFE_MAX for r in range(0, 28))
    # Once the rules found warning signs of their own, the model counts in full.
    assert model_say(0.99, BACKING_MIN, BACKING_MIN, False) == 50
    assert model_say(0.7, 30, 30, False) == 25
    # On a free hosting service the model never adds more than the limit, even when backed.
    assert model_say(0.99, 18, 8, False, shared_host=True) == MODEL_ALONE_MAX
    assert model_say(0.99, 60, 50, False, shared_host=True) == MODEL_ALONE_MAX
    assert model_say(0.45, 18, 8, False, shared_host=True) == 10
    assert model_say(0.02, 18, 8, False, shared_host=True) == -20


def test_a_limited_opinion_says_so():
    sure = m.Prediction(probability=0.97)
    risks, _ = model_reasons(sure, rule_score=0, backing=0, trusted=False)
    assert risks[0].points == MODEL_ALONE_MAX
    assert risks[0].text == (
        "The page-reading model rates this page 97% likely to be a scam page. "
        "The other checks found little to back that up, so it counts for less."
    )
    full, _ = model_reasons(sure, rule_score=BACKING_MIN, backing=BACKING_MIN, trusted=False)
    assert full[0].points == 50 and "counts for less" not in full[0].text
    hosted, _ = model_reasons(sure, rule_score=20, backing=10, trusted=False, shared_host=True)
    assert hosted[0].points == MODEL_ALONE_MAX
    assert hosted[0].text.endswith(
        "It has seen few honest pages on free hosting services, so here it counts for less."
    )


@pytest.mark.real_model
def test_the_shipped_model_fits_the_feature_list():
    """If the feature list changes and the model isn't retrained, scans would quietly run on the
    rules alone. This test is the reminder to retrain."""
    m.load.cache_clear()
    shipped = m.load()
    assert shipped is not None, "api/app/ml/model.json is missing or was trained on another feature list"
    got = shipped.predict([0.0] * len(NAMES))
    assert 0.0 <= got.probability <= 1.0
    assert shipped.meta.get("trained")

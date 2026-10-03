"""The parts of the training job that don't need LightGBM: how honest pages are weighted and how
"rules plus the model" is scored for the report."""

import math

import numpy as np

from app.analysis.score import BACKING_MIN, MODEL_ALONE_MAX
from app.ml.features import NAMES
from jobs import train

TAGS, PATH = NAMES.index("tags_log"), NAMES.index("path_length")


def pages(*rows: tuple[int, int, int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Made-up pages from (how many, tags, path length, label) rows."""
    x, y = [], []
    for count, tags, path, label in rows:
        features = [0.0] * len(NAMES)
        features[TAGS], features[PATH] = math.log1p(tags), float(path)
        x += [features] * count
        y += [label] * count
    return np.array(x, dtype=np.float32), np.array(y, dtype=np.int8)


def test_pages_are_grouped_by_size_and_bare_address():
    x, _ = pages(
        (1, 10, 1, 0), (1, 10, 14, 0), (1, 250, 1, 0), (1, 5000, 30, 0), (1, 39, 0, 0), (1, 40, 1, 0)
    )
    assert list(train.size_step(x)) == [0, 0, 2, 4, 0, 1]
    assert list(train.bare(x)) == [True, False, True, False, True, True]
    assert list(train.groups(x)) == [1, 0, 5, 8, 1, 3]
    assert len(train.SIZE_NAMES) == len(train.SIZE_EDGES) + 1


def test_honest_pages_count_for_more_where_scam_pages_outnumber_them():
    x, y = pages(
        (3, 20, 1, 0),  # small, bare address: 3 honest
        (30, 20, 1, 1),  # ... against 30 scam pages
        (1, 60, 1, 0),  # 1 honest
        (100, 60, 1, 1),  # ... against 100: the weight stops at the limit
        (50, 2000, 25, 0),  # large inner pages: honest pages already outnumber scam pages
        (5, 2000, 25, 1),
        (7, 500, 1, 1),  # a group with no honest page at all
    )
    table = train.group_weights(x, y)
    assert table[1] == {"honest": 3, "scam": 30, "weight": 10.0}
    assert table[3] == {"honest": 1, "scam": 100, "weight": train.WEIGHT_MAX}
    assert table[8] == {"honest": 50, "scam": 5, "weight": 1.0}  # never weighted down
    assert table[7] == {"honest": 0, "scam": 7, "weight": 1.0}
    assert len(table) == 2 * len(train.SIZE_NAMES)

    w = train.weights_for(x, y, table)
    assert set(w[y == 1]) == {1.0}  # scam pages always count once
    assert list(w[:3]) == [10.0] * 3 and w[33] == train.WEIGHT_MAX
    # After weighting, honest and scam pages weigh the same in the first group.
    small_bare = train.groups(x) == 1
    assert w[small_bare & (y == 0)].sum() == w[small_bare & (y == 1)].sum()


def test_the_report_scores_pages_the_way_a_scan_does():
    p = np.array([0.97, 0.97, 0.97, 0.02, 0.5])
    rules = np.array([0, BACKING_MIN, 40, 35, 12], dtype=np.int16)
    trusted = np.array([False, False, True, False, False])
    own = np.zeros(5, dtype=bool)  # none of these is on free hosting
    got = train.scan_scores(p, rules, rules, trusted, own)
    assert list(got) == [MODEL_ALONE_MAX, BACKING_MIN + 50, 40, 15, 22]
    # Without the limits the model counts in full, but still never on a trusted site.
    full = train.scan_scores(p, rules, rules, trusted, own, limit=False)
    assert list(full) == [50, BACKING_MIN + 50, 40, 15, 22]
    sure, no, yes = np.array([0.97]), np.array([False]), np.array([True])
    high = np.array([80], dtype=np.int16)
    assert train.scan_scores(np.array([0.99]), high, high, no, no)[0] == 100
    # A page whose only rule points come from free hosting: the score keeps them, the model stays limited.
    hosted, none = np.array([10], dtype=np.int16), np.array([0], dtype=np.int16)
    assert train.scan_scores(sure, hosted, none, no, yes)[0] == 10 + MODEL_ALONE_MAX
    # ... and with a minor sign on top it stops at the top of Safe (30), not above it.
    more, little = np.array([15], dtype=np.int16), np.array([5], dtype=np.int16)
    assert train.scan_scores(sure, more, little, no, yes)[0] == 30
    assert train.scan_scores(sure, more, little, no, yes, limit=False)[0] == 65
    # Backed, but on free hosting: the model adds no more than its limit.
    twenty, backed = np.array([20], dtype=np.int16), np.array([10], dtype=np.int16)
    assert train.scan_scores(sure, twenty, backed, no, yes)[0] == 20 + MODEL_ALONE_MAX
    assert train.scan_scores(sure, twenty, backed, no, no)[0] == 20 + 50


def test_rates():
    y = np.array([1, 1, 1, 0, 0, 0, 0, 0])
    flagged = np.array([1, 1, 0, 1, 0, 0, 0, 0])
    r = train.rates(y, flagged)
    assert (r["tp"], r["fp"], r["fn"], r["tn"]) == (2, 1, 1, 4)
    assert r["precision"] == 2 / 3 and r["recall"] == 2 / 3 and r["false_alarms"] == 1 / 5
    assert train.rates(y, np.zeros(8, dtype=int))["precision"] == 0.0


def test_no_saved_honest_pages_is_said_plainly():
    lines, summary_line = train.honest_section(None)
    assert summary_line is None
    assert "Not checked in this run" in " ".join(lines)

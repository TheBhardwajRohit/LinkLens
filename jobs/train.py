"""Train the page-reading model and write an honest report about how good it is.

Input: the feature files the dataset loader wrote (/data/ml/phreshphish-train and -test).
Output: the model as plain JSON (trees as flat lists, used by api/app/ml/model.py without
LightGBM) and docs/MODEL_REPORT.md.

How it is checked:
- The newest 15% of the training rows (by date) are held back to decide when to stop adding trees.
- The dataset's own test split is never used for training or tuning. Every number in the report's
  tables comes from it.
- The plain-Python tree walker must give the same answers as LightGBM itself, or the job fails.
- "Rules plus the model" is scored with the scan's own function (`model_say`), so the report shows
  what a scan would do.
- If real honest pages were collected (`jobs.honest_check`), the report says how the model rates
  those too.

One thing the dataset gets wrong is corrected here. Its honest pages are mostly large inner pages
of popular sites and its scam pages are mostly small pages at a bare site address. Left alone, a
model learns "small page" and "bare address" as signs of a scam. `group_weights` makes honest pages
count for more wherever scam pages outnumber them, so those two facts say nothing on their own.

    python -m jobs.train --out-model api/app/ml/model.json --out-report docs/MODEL_REPORT.md
"""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from app.analysis.score import BACKING_MIN, MODEL_ALONE_MAX, SAFE_MAX, SUSPICIOUS_MAX, model_say
from app.ml.features import NAMES
from app.ml.model import PLAIN, TreeModel, model_points
from jobs import honest_check
from jobs.common import say

PARAMS = {
    "objective": "binary",
    "learning_rate": 0.06,
    "num_leaves": 31,
    "min_child_samples": 40,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "verbose": -1,
    "seed": 7,
}
MAX_TREES = 300
PATIENCE = 30
HOLD_BACK = 0.15

# Pages are grouped by size (tags on the page) and by whether the link is a bare site address.
SIZE_EDGES = (40, 100, 300, 1000)
SIZE_NAMES = ("under 40", "40 to 99", "100 to 299", "300 to 999", "1,000 or more")
# An honest page never counts for more than this many pages, however rare its group is.
WEIGHT_MAX = 20.0
TAGS, PATH = NAMES.index("tags_log"), NAMES.index("path_length")
# Facts kept next to the features that are not features themselves.
EXTRA = ("rule_score", "backing", "trusted", "has_query", "free_hosting")


def read(folder: Path) -> dict:
    import pyarrow.parquet as pq

    files = sorted(folder.glob("part-*.parquet"))
    if not files:
        raise SystemExit(f"No feature files in {folder}. Run jobs.seed_phreshphish first.")
    table = pq.read_table(files)
    missing = [name for name in (*NAMES, *EXTRA) if name not in table.column_names]
    if missing:
        raise SystemExit(
            f"The feature files in {folder} were written by older code (no '{missing[0]}' column). "
            "Run jobs.seed_phreshphish again for both splits."
        )
    order = np.argsort(np.array(table["date"].to_pylist(), dtype=object), kind="stable")
    features = np.column_stack([table[name].to_numpy() for name in NAMES]).astype(np.float32)

    def flags(name: str) -> np.ndarray:
        return np.array(table[name].to_pylist(), dtype=bool)[order]

    return {
        "x": features[order],
        "y": table["label"].to_numpy().astype(np.int8)[order],
        "date": np.array(table["date"].to_pylist(), dtype=object)[order],
        "rule_score": table["rule_score"].to_numpy().astype(np.int16)[order],
        "backing": table["backing"].to_numpy().astype(np.int16)[order],
        "free_hosting": flags("free_hosting"),
        "trusted": flags("trusted"),
        "has_query": flags("has_query"),
        "site": np.array(table["site"].to_pylist(), dtype=object)[order],
    }


def size_step(x: np.ndarray) -> np.ndarray:
    """0 for the smallest pages up to 4 for the largest (see SIZE_NAMES)."""
    return np.digitize(np.expm1(x[:, TAGS]), SIZE_EDGES)


def bare(x: np.ndarray) -> np.ndarray:
    """True where the link is a bare site address: nothing, or only "/", after the site name."""
    return x[:, PATH] < 2


def groups(x: np.ndarray) -> np.ndarray:
    return size_step(x) * 2 + bare(x)


def group_weights(x: np.ndarray, y: np.ndarray) -> dict[int, dict]:
    """For each group: how many honest and scam pages it holds, and how much each honest page
    counts in training. Where scam pages outnumber honest ones, honest pages are weighted up until
    both sides weigh the same (or WEIGHT_MAX is reached). Nothing is ever weighted down."""
    g = groups(x)
    table = {}
    for k in range(2 * len(SIZE_NAMES)):
        honest = int(((g == k) & (y == 0)).sum())
        scam = int(((g == k) & (y == 1)).sum())
        weight = min(max(scam / honest, 1.0), WEIGHT_MAX) if honest else 1.0
        table[k] = {"honest": honest, "scam": scam, "weight": round(weight, 2)}
    return table


def weights_for(x: np.ndarray, y: np.ndarray, table: dict[int, dict]) -> np.ndarray:
    g = groups(x)
    w = np.ones(len(y))
    for k, row in table.items():
        w[(g == k) & (y == 0)] = row["weight"]
    return w


def scan_scores(
    p: np.ndarray,
    rule_score: np.ndarray,
    backing: np.ndarray,
    trusted: np.ndarray,
    shared_host: np.ndarray,
    limit: bool = True,
) -> np.ndarray:
    """The score a scan would give each page: what the rules found plus what the model may add.
    `limit=False` lets the model count in full wherever it isn't a trusted site, to show what the
    limits cost."""
    added = [
        model_say(float(pi), int(r), int(b) if limit else 100, bool(t), bool(h) and limit)
        for pi, r, b, t, h in zip(p, rule_score, backing, trusted, shared_host, strict=True)
    ]
    return np.clip(rule_score.astype(int) + np.array(added), 0, 100)


def flatten(tree: dict) -> dict:
    """LightGBM's nested tree as five flat lists (see TreeModel)."""
    f: list[int] = []
    t: list[float] = []
    left: list[int] = []
    right: list[int] = []
    v: list[float] = []

    def walk(node: dict) -> int:
        index = len(f)
        f.append(-1)
        t.append(0.0)
        left.append(-1)
        right.append(-1)
        if "leaf_value" in node:
            v.append(round(float(node["leaf_value"]), 6))
            return index
        if node.get("decision_type") != "<=":
            raise SystemExit("The model has a split this code can't walk (not a simple <= split).")
        v.append(round(float(node["internal_value"]), 6))
        f[index] = int(node["split_feature"])
        t[index] = float(np.float32(node["threshold"]))
        left[index] = walk(node["left_child"])
        right[index] = walk(node["right_child"])
        return index

    walk(tree)
    return {"f": f, "t": t, "l": left, "r": right, "v": v}


def rates(y: np.ndarray, flagged: np.ndarray) -> dict:
    tp = int(((flagged == 1) & (y == 1)).sum())
    fp = int(((flagged == 1) & (y == 0)).sum())
    fn = int(((flagged == 0) & (y == 1)).sum())
    tn = int(((flagged == 0) & (y == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "false_alarms": fp / (fp + tn) if fp + tn else 0.0,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def row(name: str, r: dict) -> str:
    return (
        f"| {name} | {pct(r['precision'])} | {pct(r['recall'])} | {pct(r['f1'])} | {pct(r['false_alarms'])} |"
        f" {r['tp']:,} | {r['fp']:,} | {r['fn']:,} |"
    )


def share(mask: np.ndarray, y: np.ndarray, label: int) -> str:
    return pct(float(mask[y == label].mean()))


def honest_section(s: dict | None) -> tuple[list[str], str | None]:
    """The report's part about real honest pages, and one line for the summary at the top.
    `s` is `honest_check.summary` of the saved pages, or None when there are none."""
    if not s:
        return (
            [
                "## Real honest pages from outside the dataset",
                "",
                "Not checked in this run: no saved pages were found. `python -m jobs.honest_check collect`",
                "scans the list in `jobs/data/honest_sites.txt` through a running scan server and saves them.",
                "",
            ],
            None,
        )
    small = honest_check.SMALL_PAGE
    still_above = []
    if s["above_safe_sites"]:
        named = ", ".join(
            f"`{site.split('//')[-1].rstrip('/')}` (score {score})" for site, score in s["above_safe_sites"]
        )
        still_above = [f"Still above Safe: {named}.", ""]
    lines = [
        "## Real honest pages from outside the dataset",
        "",
        f"{s['pages']} well-known honest pages (small personal sites, software project pages, login pages, pages on",
        "free hosting, Indian government services; the list is `jobs/data/honest_sites.txt`) were scanned through the",
        f"local scan server, last on {s['scanned']}. The numbers the model reads were saved by",
        "`jobs/honest_check.py`, so this part is worked out again every time the model is trained.",
        "",
        "| | Pages |",
        "|---|---|",
        f"| Honest pages checked | {s['pages']} |",
        f"| Rated 40% or more likely to be a scam page | {s['at_40']} |",
        f"| Rated 60% or more | {s['at_60']} |",
        f"| Rated 80% or more | {s['at_80']} |",
        f"| Rated 95% or more | {s['at_95']} |",
        f"| Above Safe in a scan (rules, model, and the limit together) | {s['above_safe']} |",
        f"| Above Safe if the model always counted in full | {s['unlimited_above_safe']} |",
        "",
        f"{s['small_at_60']} of the {s['at_60']} pages rated 60% or more have under {small} tags ({s['small']} pages that small were",
        "checked). Very small honest pages are the model's weak spot, and the reason it cannot raise a",
        "verdict alone.",
        "",
        *still_above,
        "This is a sanity check, not a clean test. The list is short and hand-picked, and it was looked at",
        "while the fixes above were chosen.",
        "",
    ]
    line = (
        f"- On {s['pages']} real honest pages from outside the dataset, the model alone rates {s['at_60']} as likely"
        f" scams (60% or more). In a scan, {s['above_safe']} of them {'ends' if s['above_safe'] == 1 else 'end'} up above Safe."
    )
    return lines, line


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--features-dir", default=os.environ.get("FEATURES_DIR", "/data/ml"))
    parser.add_argument("--out-model", default="/data/ml/model.json")
    parser.add_argument("--out-report", default="/data/ml/MODEL_REPORT.md")
    args = parser.parse_args()

    import lightgbm as lgb
    from sklearn.metrics import average_precision_score, roc_auc_score

    base = Path(args.features_dir)
    train, test = read(base / "phreshphish-train"), read(base / "phreshphish-test")
    cut = int(len(train["y"]) * (1 - HOLD_BACK))
    say(
        f"Training rows: {cut:,}, held back to decide when to stop: {len(train['y']) - cut:,}, test: {len(test['y']):,}"
    )

    # Weights come from the rows the model is fitted on; the held-back rows use the same table.
    table = group_weights(train["x"][:cut], train["y"][:cut])

    def fit_trees(weighted: bool):
        """Train on the older rows, stop when the newer, held-back rows stop improving."""
        parts = []
        for rows in (slice(0, cut), slice(cut, None)):
            x, labels = train["x"][rows], train["y"][rows]
            parts.append(
                lgb.Dataset(
                    x,
                    labels,
                    weight=weights_for(x, labels, table) if weighted else None,
                    feature_name=NAMES,
                    reference=parts[0] if parts else None,
                )
            )
        made = lgb.train(
            PARAMS,
            parts[0],
            num_boost_round=MAX_TREES,
            valid_sets=[parts[1]],
            callbacks=[lgb.early_stopping(PATIENCE, verbose=False)],
        )
        count = made.best_iteration or made.current_iteration()
        lists = [flatten(t["tree_structure"]) for t in made.dump_model(num_iteration=count)["tree_info"]]
        return made, count, lists

    booster, trees, tree_lists = fit_trees(weighted=True)
    trained = datetime.now(UTC).date().isoformat()
    model = {
        "features": NAMES,
        "base": 0.0,
        "trees": tree_lists,
        "meta": {
            "trained": trained,
            "trees": trees,
            "train_rows": cut,
            "data": "PhreshPhish v1.0.1 (CC BY 4.0)",
            "weights": "honest pages weighted up by page size and bare address, see docs/MODEL_REPORT.md",
        },
    }

    # The plain-Python walker must agree with LightGBM itself.
    walker = TreeModel(model)
    theirs = booster.predict(test["x"][:400], num_iteration=trees, raw_score=True)
    ours = np.array([walker.raw([float(v) for v in x])[0] for x in test["x"][:400]])
    worst = float(np.abs(theirs - ours).max())
    if worst > 1e-3:
        raise SystemExit(f"The plain-Python model disagrees with LightGBM (off by {worst:.5f}).")
    say(f"Plain-Python model matches LightGBM on 400 test pages (largest difference {worst:.6f}).")

    y = test["y"]
    p = booster.predict(test["x"], num_iteration=trees)
    auc, pr_auc = roc_auc_score(y, p), average_precision_score(y, p)
    at = {cutoff: rates(y, (p >= cutoff).astype(int)) for cutoff in (0.95, 0.8, 0.6, 0.5, 0.4)}
    low = {
        cutoff: float(((p <= cutoff) & (y == 1)).sum() / max((p <= cutoff).sum(), 1))
        for cutoff in (0.05, 0.15)
    }

    rules = test["rule_score"].astype(int)
    scored = (test["rule_score"], test["backing"], test["trusted"], test["free_hosting"])
    both = scan_scores(p, *scored)
    unlimited = scan_scores(p, *scored, limit=False)
    compare = {
        "rules_suspicious": rates(y, (rules > SAFE_MAX).astype(int)),
        "both_suspicious": rates(y, (both > SAFE_MAX).astype(int)),
        "unlimited_suspicious": rates(y, (unlimited > SAFE_MAX).astype(int)),
        "rules_dangerous": rates(y, (rules > SUSPICIOUS_MAX).astype(int)),
        "both_dangerous": rates(y, (both > SUSPICIOUS_MAX).astype(int)),
    }
    trusted_scams = int((test["trusted"] & (y == 1)).sum())
    # Pages on sites the model has never seen any page of, in training or in the held-back part.
    fresh = ~np.isin(test["site"], np.unique(train["site"]))
    at_fresh = rates(y[fresh], (p[fresh] >= 0.5).astype(int))

    step = size_step(test["x"])
    sizes = []
    for k, name in enumerate(SIZE_NAMES):
        honest, scam = (step == k) & (y == 0), (step == k) & (y == 1)
        sizes.append(
            f"| {name} | {int(honest.sum()):,} | {int((honest & (p >= 0.5)).sum()):,} ({pct((honest & (p >= 0.5)).sum() / max(honest.sum(), 1))}) |"
            f" {int(scam.sum()):,} | {int((scam & (p >= 0.5)).sum()):,} ({pct((scam & (p >= 0.5)).sum() / max(scam.sum(), 1))}) |"
        )

    gain = booster.feature_importance(importance_type="gain", iteration=trees)
    top = sorted(zip(NAMES, gain / gain.sum(), strict=True), key=lambda item: -item[1])[:15]

    honest_rows = honest_check.load(base / "honest-sites.jsonl")
    real = honest_check.summary(honest_check.rate(honest_rows, walker)) if honest_rows else None
    honest_lines, honest_line = honest_section(real)

    # The same model trained without the weights, only to show what they change.
    plain, plain_trees, plain_lists = fit_trees(weighted=False)
    plain_p = plain.predict(test["x"], num_iteration=plain_trees)
    plain_at = rates(y, (plain_p >= 0.5).astype(int))
    small_honest_test = (step <= 1) & (y == 0)
    change = [
        f"| Scam pages caught (50% cut-off) | {pct(plain_at['recall'])} | {pct(at[0.5]['recall'])} |",
        f"| Honest pages wrongly flagged | {pct(plain_at['false_alarms'])} | {pct(at[0.5]['false_alarms'])} |",
        f"| Honest pages under 100 tags wrongly flagged ({int(small_honest_test.sum()):,} in the test set) |"
        f" {pct((plain_p[small_honest_test] >= 0.5).mean())} | {pct((p[small_honest_test] >= 0.5).mean())} |",
    ]
    if honest_rows:
        plain_walker = TreeModel({"features": NAMES, "trees": plain_lists})
        real_plain = honest_check.summary(honest_check.rate(honest_rows, plain_walker))
        change.append(
            f"| Real honest pages rated 60% or more likely scam (of {real['pages']}, see below) |"
            f" {real_plain['at_60']} | {real['at_60']} |"
        )

    model["meta"].update(
        {
            "test_rows": int(len(y)),
            "roc_auc": round(float(auc), 4),
            "precision_at_half": round(at[0.5]["precision"], 4),
            "recall_at_half": round(at[0.5]["recall"], 4),
        }
    )
    out_model = Path(args.out_model)
    out_model.parent.mkdir(parents=True, exist_ok=True)
    out_model.write_text(json.dumps(model, separators=(",", ":")), encoding="utf-8")
    say(f"Model: {trees} trees, {out_model.stat().st_size / 1024:.0f} kB, written to {out_model}")

    tx, ty = train["x"], train["y"]
    small_honest = int(((size_step(tx[:cut]) == 0) & (ty[:cut] == 0)).sum())
    query_honest = int((train["has_query"] & (ty == 0)).sum())
    free_honest = int((train["free_hosting"] & (ty == 0)).sum())
    header = (
        "| | Precision | Recall | F1 | False alarms | Scams caught | Honest pages flagged | Scams missed |"
    )
    lines = [
        "# Model report",
        "",
        f"Written by `jobs/train.py` on {trained}. Results are measured on pages the model never saw.",
        "",
        "## In short",
        "",
        f"- The model reads only the link and the page (the {len(NAMES)} numbers in `api/app/ml/features.py`).",
        f"- At its default cut-off (50%), it catches {pct(at[0.5]['recall'])} of the scam pages in the test set,",
        f"  and {pct(at[0.5]['precision'])} of the pages it flags really are scams. It wrongly flags {pct(at[0.5]['false_alarms'])} of honest pages.",
        "- It is not trusted on its own. In a scan it can lift a page out of Safe only when the plain rules",
        f"  found warning signs too. Scored that way, rules and model together mark {pct(compare['both_suspicious']['recall'])} of the test",
        f"  set's scam pages Suspicious or worse, and {pct(compare['both_suspicious']['false_alarms'])} of its honest pages.",
        *([honest_line] if honest_line else []),
        '- These are results on a research dataset. Real links are harder, so the report page still says "likely".',
        "",
        "Words used here: *precision* is the share of flagged pages that really are scams. *Recall* is the",
        "share of all scams that were caught. *False alarms* is the share of honest pages wrongly flagged.",
        "",
        "## Data",
        "",
        "PhreshPhish v1.0.1 (CC BY 4.0), streamed and reduced to feature numbers by `jobs/seed_phreshphish.py`.",
        "",
        "| Part | Pages | Scam | Honest | Dates |",
        "|---|---|---|---|---|",
        f"| Training | {cut:,} | {int(ty[:cut].sum()):,} | {cut - int(ty[:cut].sum()):,} |"
        f" {train['date'][0]} to {train['date'][cut - 1]} |",
        f"| Held back (to decide when to stop) | {len(ty) - cut:,} | {int(ty[cut:].sum()):,} |"
        f" {len(ty) - cut - int(ty[cut:].sum()):,} | {train['date'][cut]} to {train['date'][-1]} |",
        f"| Test (the dataset's own test split) | {len(y):,} | {int(y.sum()):,} | {len(y) - int(y.sum()):,} |"
        f" {test['date'][0]} to {test['date'][-1]} |",
        "",
        "## What the dataset gets wrong, and what was done about it",
        "",
        "The honest pages in the dataset are not like the honest pages people paste into a link checker.",
        "They are mostly large inner pages of popular sites, while the scam pages are mostly small pages at",
        "a bare site address:",
        "",
        "| In the training data | Honest pages | Scam pages |",
        "|---|---|---|",
        f"| The link is a bare site address (nothing after the site name) | {share(bare(tx), ty, 0)} | {share(bare(tx), ty, 1)} |",
        f'| The link has a query string (a part after "?") | {share(train["has_query"], ty, 0)} ({query_honest:,} of {int((ty == 0).sum()):,}) | {share(train["has_query"], ty, 1)} |',
        f"| The page has under 100 tags | {share(size_step(tx) <= 1, ty, 0)} | {share(size_step(tx) <= 1, ty, 1)} |",
        f"| The site is on a free hosting service (github.io, weebly.com and the like) | {share(train['free_hosting'], ty, 0)} ({free_honest:,} of {int((ty == 0).sum()):,}) | {share(train['free_hosting'], ty, 1)} |",
        "",
        "A model trained on this as it is learns shortcuts that hold in the dataset but not on the web:",
        "a query string, a bare address, a small page, or free hosting each means scam. Earlier versions",
        "of this model did. The first called every one of 63 real honest pages a likely scam as soon as a",
        'newsletter tag ("?utm_source=...") was added to its link. A later one, which still knew whether a',
        "site was on free hosting, rated 8 of 17 real honest pages on github.io and similar services as",
        "likely scams. Three things were done:",
        "",
        "1. **The model never sees the query string**, nor the length of the whole link (which gives the",
        "   query string away), nor whether the site is on a free hosting service. The dataset has next",
        "   to no honest examples of either, so no weighting could fix them. The rules still use both,",
        "   in the open.",
        "2. **Honest pages count for more where they are rare.** Pages are grouped by size and by whether",
        "   the link is a bare address. In a group where scam pages outnumber honest ones, each honest page",
        f"   is weighted up (at most {WEIGHT_MAX:.0f} times) until both sides weigh the same. Being small, or being a bare",
        "   address, then says nothing on its own. The groups are listed below.",
        '3. **The model cannot raise a verdict alone.** See "Rules alone, and rules plus the model".',
        "",
        "| Page size (tags) | Link | Honest pages | Scam pages | Each honest page counts as |",
        "|---|---|---|---|---|",
        *[
            f"| {SIZE_NAMES[k // 2]} | {'bare address' if k % 2 else 'inner page'} | {r['honest']:,} | {r['scam']:,} | {r['weight']:g} |"
            for k, r in table.items()
        ],
        "",
        "What the weights change, with everything else kept the same:",
        "",
        "| | Without the weights | With the weights |",
        "|---|---|---|",
        *change,
        "",
        "## Model",
        "",
        f"Gradient-boosted decision trees (LightGBM), {trees} trees of up to {PARAMS['num_leaves']} leaves, learning",
        f"rate {PARAMS['learning_rate']}. Training stopped when {PATIENCE} more trees no longer helped on the held-back",
        "pages. The model ships as plain JSON and is run by about 40 lines of Python, checked against LightGBM.",
        "",
        "## Results on the test set",
        "",
        f"- ROC AUC: {auc:.4f} (1.0 is perfect ranking, 0.5 is guessing)",
        f"- PR AUC: {pr_auc:.4f}",
        "",
        "At different cut-offs of the model's probability:",
        "",
        header,
        "|---|---|---|---|---|---|---|---|",
        *[row(f"Flag when at least {int(c * 100)}%", at[c]) for c in (0.95, 0.8, 0.6, 0.5, 0.4)],
        "",
        f"When the model says 5% or less, {pct(low[0.05])} of those pages are scams anyway.",
        f"When it says 15% or less, {pct(low[0.15])} are.",
        "",
        "The same test pages by size, at the 50% cut-off:",
        "",
        "| Page size (tags) | Honest pages | Wrongly flagged | Scam pages | Caught |",
        "|---|---|---|---|---|",
        *sizes,
        "",
        "Small honest pages are still flagged far more often than large ones, and the test set holds few",
        "of them, so those percentages are rough.",
        "",
        f"{int(fresh.sum()):,} of the test pages ({int((fresh & (y == 1)).sum()):,} scam, {int((fresh & (y == 0)).sum()):,} honest) are on sites that have no page at all in the",
        f"training data. On those alone, at the 50% cut-off, the model catches {pct(at_fresh['recall'])} of the scam pages and",
        f"wrongly flags {pct(at_fresh['false_alarms'])} of the honest ones.",
        "",
        "## Rules alone, and rules plus the model",
        "",
        "The rule score here uses the link and page only (a dataset has no domain age, certificate,",
        "blacklists, or scam family), so live scans have more to go on than this table shows.",
        "",
        "How the model's opinion is added (`model_say` in `api/app/analysis/score.py`, the function a scan uses):",
        "",
        f"- 95% or more adds {model_points(0.95)} points, 80% adds {model_points(0.8)}, 60% adds {model_points(0.6)}, 40% adds {model_points(0.4)}."
        f" 15% or less takes {-model_points(0.15)} off, 5% or less takes {-model_points(0.05)} off.",
        f"- When the rules alone scored under {BACKING_MIN} (not counting the points for free hosting, which honest and",
        f"  scam sites share), the model may add at most {MODEL_ALONE_MAX}, and never enough to leave",
        f"  Safe (0 to {SAFE_MAX}).",
        f"- On a free hosting service the model never adds more than {MODEL_ALONE_MAX}, backed or not. The training data",
        f"  has {free_honest:,} honest pages hosted that way, so there the model cannot tell honest from scam.",
        "- On a brand's real site, or one of the 10,000 most visited sites, the model never adds points.",
        f"  {trusted_scams:,} of the test set's {int(y.sum()):,} scam pages sit on such sites.",
        "",
        header,
        "|---|---|---|---|---|---|---|---|",
        row("Rules alone: Suspicious or worse (31+)", compare["rules_suspicious"]),
        row("Rules + model: Suspicious or worse (31+)", compare["both_suspicious"]),
        row("Rules alone: Likely dangerous (70+)", compare["rules_dangerous"]),
        row("Rules + model: Likely dangerous (70+)", compare["both_dangerous"]),
        "",
        f"If the model always counted in full (no limits but the last one), the second row would catch {pct(compare['unlimited_suspicious']['recall'])} of the scam pages",
        f"and flag {pct(compare['unlimited_suspicious']['false_alarms'])} of the honest ones. The difference is the price of not letting the model",
        "raise a verdict alone. It looks large here because most scam pages in a dataset show no other",
        "warning sign: there is no domain age, certificate, blacklist, or family to look at. A live scan",
        "has those.",
        "",
        *honest_lines,
        "## What the model leans on most",
        "",
        "| Signal | Share of the model's total gain |",
        "|---|---|",
        *[
            f"| {PLAIN.get(name, name.replace('_', ' '))} (`{name}`) | {pct(share_)} |"
            for name, share_ in top
        ],
        "",
        "## Honest limits",
        "",
        "- The weights reduce what the model learns from page size, but they cannot add what is missing:",
        f"  the training data holds only {small_honest:,} honest pages under 40 tags.",
        "- The limit on the model costs recall. A scam page that shows no other warning sign is not",
        "  flagged by the model alone.",
        "- Scam kits are copied many times. Copies of one kit can sit in both the training and the test",
        "  set, which makes the test easier than brand-new kits would be.",
        "- The model sees the page as the sandbox captured it. Pages that show different content to",
        "  scanners are judged on what was shown. On a bot-check screen the model says nothing.",
        "- It does not use who registered the domain, the server, blacklists, or scam families. Those are",
        "  added by the rules, which is why the final score combines both.",
        "- Popularity, the query string, and free hosting are left out of the model on purpose (see",
        "  `api/app/ml/features.py`).",
        "",
    ]
    out_report = Path(args.out_report)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text("\n".join(lines), encoding="utf-8")
    say(f"Report written to {out_report}")
    say(
        f"Test set: ROC AUC {auc:.4f}; at 50%: precision {pct(at[0.5]['precision'])}, recall {pct(at[0.5]['recall'])}"
    )


if __name__ == "__main__":
    main()

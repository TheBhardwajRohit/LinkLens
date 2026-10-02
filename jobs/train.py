"""Train the page-reading model and write an honest report about how good it is.

Input: the feature files the dataset loader wrote (/data/ml/phreshphish-train and -test).
Output: the model as plain JSON (trees as flat lists, used by api/app/ml/model.py without
LightGBM) and docs/MODEL_REPORT.md.

How it is checked:
- The newest 15% of the training rows (by date) are held back to decide when to stop adding trees.
- The dataset's own test split is never used for training or tuning. Every number in the report
  comes from it.
- The plain-Python tree walker must give the same answers as LightGBM itself, or the job fails.

    python -m jobs.train --out-model api/app/ml/model.json --out-report docs/MODEL_REPORT.md
"""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from app.analysis.score import SAFE_MAX, SUSPICIOUS_MAX
from app.ml.features import NAMES
from app.ml.model import PLAIN, TreeModel, model_points
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


def read(folder: Path) -> dict:
    import pyarrow.parquet as pq

    files = sorted(folder.glob("part-*.parquet"))
    if not files:
        raise SystemExit(f"No feature files in {folder}. Run jobs.seed_phreshphish first.")
    table = pq.read_table(files)
    order = np.argsort(np.array(table["date"].to_pylist(), dtype=object), kind="stable")
    features = np.column_stack([table[name].to_numpy() for name in NAMES]).astype(np.float32)
    return {
        "x": features[order],
        "y": table["label"].to_numpy().astype(np.int8)[order],
        "date": np.array(table["date"].to_pylist(), dtype=object)[order],
        "rule_score": table["rule_score"].to_numpy().astype(np.int16)[order],
    }


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

    fit = lgb.Dataset(train["x"][:cut], train["y"][:cut], feature_name=NAMES)
    hold = lgb.Dataset(train["x"][cut:], train["y"][cut:], feature_name=NAMES, reference=fit)
    booster = lgb.train(
        PARAMS,
        fit,
        num_boost_round=MAX_TREES,
        valid_sets=[hold],
        callbacks=[lgb.early_stopping(PATIENCE, verbose=False)],
    )
    trees = booster.best_iteration or booster.current_iteration()
    dump = booster.dump_model(num_iteration=trees)
    trained = datetime.now(UTC).date().isoformat()
    model = {
        "features": NAMES,
        "base": 0.0,
        "trees": [flatten(t["tree_structure"]) for t in dump["tree_info"]],
        "meta": {
            "trained": trained,
            "trees": trees,
            "train_rows": cut,
            "data": "PhreshPhish v1.0.1 (CC BY 4.0)",
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
    points = np.array([model_points(float(v)) for v in p])
    both = np.clip(rules + points, 0, 100)
    compare = {
        "rules_suspicious": rates(y, (rules > SAFE_MAX).astype(int)),
        "both_suspicious": rates(y, (both > SAFE_MAX).astype(int)),
        "rules_dangerous": rates(y, (rules > SUSPICIOUS_MAX).astype(int)),
        "both_dangerous": rates(y, (both > SUSPICIOUS_MAX).astype(int)),
    }

    gain = booster.feature_importance(importance_type="gain", iteration=trees)
    top = sorted(zip(NAMES, gain / gain.sum(), strict=True), key=lambda item: -item[1])[:15]

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

    header = (
        "| | Precision | Recall | F1 | False alarms | Scams caught | Honest pages flagged | Scams missed |"
    )
    lines = [
        "# Model report",
        "",
        f"Written by `jobs/train.py` on {trained}. Every number below comes from pages the model never saw.",
        "",
        "## In short",
        "",
        f"- The model reads only the link and the page (the {len(NAMES)} numbers in `api/app/ml/features.py`).",
        f"- At its default cut-off (50%), it catches {pct(at[0.5]['recall'])} of the scam pages in the test set,",
        f"  and {pct(at[0.5]['precision'])} of the pages it flags really are scams.",
        f"- It wrongly flags {pct(at[0.5]['false_alarms'])} of honest pages.",
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
        f"| Training | {cut:,} | {int(train['y'][:cut].sum()):,} | {cut - int(train['y'][:cut].sum()):,} |"
        f" {train['date'][0]} to {train['date'][cut - 1]} |",
        f"| Held back (to decide when to stop) | {len(train['y']) - cut:,} | {int(train['y'][cut:].sum()):,} |"
        f" {len(train['y']) - cut - int(train['y'][cut:].sum()):,} | {train['date'][cut]} to {train['date'][-1]} |",
        f"| Test (the dataset's own test split) | {len(y):,} | {int(y.sum()):,} | {len(y) - int(y.sum()):,} |"
        f" {test['date'][0]} to {test['date'][-1]} |",
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
        "## Rules alone, and rules plus the model",
        "",
        "The rule score here uses the link and page only (a dataset has no domain age, blacklists, or",
        "family), so live scans have more to go on than this table shows. The model adds or removes points",
        "(see `model_points` in `api/app/ml/model.py`).",
        "",
        header,
        "|---|---|---|---|---|---|---|---|",
        row("Rules alone: Suspicious or worse (31+)", compare["rules_suspicious"]),
        row("Rules + model: Suspicious or worse (31+)", compare["both_suspicious"]),
        row("Rules alone: Likely dangerous (70+)", compare["rules_dangerous"]),
        row("Rules + model: Likely dangerous (70+)", compare["both_dangerous"]),
        "",
        "## What the model leans on most",
        "",
        "| Signal | Share of the model's total gain |",
        "|---|---|",
        *[f"| {PLAIN.get(name, name.replace('_', ' '))} (`{name}`) | {pct(share)} |" for name, share in top],
        "",
        "## Honest limits",
        "",
        "- The honest pages in the dataset are mostly popular, well-built sites. A small honest site with a",
        "  login form looks more like the scam pages than those do, so real false alarms will be higher.",
        "- Scam kits are copied many times. Copies of one kit can sit in both the training and the test",
        "  set, which makes the test easier than brand-new kits would be.",
        "- The model sees the page as the sandbox captured it. Pages that hide behind bot checks, or show",
        "  different content to scanners, are judged on what was shown.",
        "- It does not use who registered the domain, the server, blacklists, or scam families. Those are",
        "  added by the rules, which is why the final score combines both.",
        "- Popularity is left out of the model on purpose (see `api/app/ml/features.py`).",
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

"""Check the model on real honest pages from outside the dataset.

The dataset's honest pages are mostly large inner pages of popular sites, so its test split says
little about a small honest site. This job sends a list of well-known honest pages
(jobs/data/honest_sites.txt) to a running scan server, which opens them in its sandbox as usual,
and keeps the numbers the model reads. `jobs.train` then reports how the model rates them.

Nothing here opens a site itself; only the scan server's sandbox does. No HTML is kept.

    python -m jobs.honest_check collect --api http://api:8000     (API key in LINKLENS_API_KEY)
    python -m jobs.honest_check report
"""

import argparse
import json
import os
from pathlib import Path

import httpx

from app.analysis import is_bot_screen, is_trusted
from app.analysis.content import PageFeatures
from app.analysis.lexical import LinkFeatures
from app.analysis.scamtype import impersonated_brands
from app.analysis.score import SAFE_MAX, model_say
from app.fingerprint import Fingerprints
from app.ml import model as page_model
from app.ml.features import vector
from jobs.common import now, say

SITES = Path(__file__).parent / "data" / "honest_sites.txt"
SMALL_PAGE = 40  # tags


def read_list(path: Path = SITES) -> list[str]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def row_from_scan(site: str, scan: dict) -> dict | None:
    """What to keep from one scan: the link and page facts the model reads, plus what the rules
    alone scored. None when the page wasn't captured, or when all the sandbox saw was a bot-check
    screen (the model never speaks about those, see `app.analysis.analyze`)."""
    analysis = scan.get("analysis") or {}
    page = analysis.get("page") or {}
    prints = scan.get("fingerprints") or {}
    if not page.get("captured"):
        return None
    bot_check = (scan.get("visit") or {}).get("bot_check")
    if is_bot_screen(bot_check, PageFeatures.model_validate(page), prints.get("words")):
        return None
    link = analysis.get("final_link") or analysis.get("link")
    if "backing" not in analysis:
        raise SystemExit("The scan server runs older code than this job. Rebuild and restart it first.")
    return {
        "site": site,
        "scanned": now().date().isoformat(),
        "link": link,
        "page": page,
        "tags": prints.get("tags", 0),
        "words": prints.get("words", 0),
        "out_domains": prints.get("out_domains") or [],
        "rule_score": analysis["rule_score"],
        "backing": analysis["backing"],
    }


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def features(row: dict) -> tuple[list[float], LinkFeatures]:
    """The model's numbers for a saved page, built with today's feature code."""
    link = LinkFeatures.model_validate(row["link"])
    page = PageFeatures.model_validate(row["page"])
    prints = Fingerprints(tags=row["tags"], words=row["words"], out_domains=row["out_domains"])
    copied = impersonated_brands(link, page, link.host, link.registered_domain)
    return vector(link, page, prints, len(copied)), link


def rate(rows: list[dict], model: page_model.TreeModel) -> list[dict]:
    """What the model says about each saved page and where the score ends up, worked out the way a
    scan does it."""
    rated = []
    for row in rows:
        x, link = features(row)
        probability = model.predict(x).probability
        trusted = is_trusted(link)
        shared = link.free_hosting is not None
        rated.append(
            {
                "site": row["site"],
                "scanned": row.get("scanned", ""),
                "tags": row["tags"],
                "trusted": trusted,
                "probability": probability,
                "rule_score": row["rule_score"],
                "score": max(
                    0,
                    min(
                        100,
                        row["rule_score"]
                        + model_say(probability, row["rule_score"], row["backing"], trusted, shared),
                    ),
                ),
                # What the score would be if the model counted in full whatever the rules found.
                "unlimited": max(
                    0, min(100, row["rule_score"] + model_say(probability, row["rule_score"], 100, trusted))
                ),
            }
        )
    return rated


def summary(rated: list[dict]) -> dict:
    def count(test) -> int:
        return sum(1 for r in rated if test(r))

    return {
        "pages": len(rated),
        "at_40": count(lambda r: r["probability"] >= 0.4),
        "at_60": count(lambda r: r["probability"] >= 0.6),
        "at_80": count(lambda r: r["probability"] >= 0.8),
        "at_95": count(lambda r: r["probability"] >= 0.95),
        "small": count(lambda r: r["tags"] < SMALL_PAGE),
        "small_at_60": count(lambda r: r["tags"] < SMALL_PAGE and r["probability"] >= 0.6),
        "trusted": count(lambda r: r["trusted"]),
        "above_safe": count(lambda r: r["score"] > SAFE_MAX),
        "above_safe_sites": [(r["site"], r["score"]) for r in rated if r["score"] > SAFE_MAX],
        "unlimited_above_safe": count(lambda r: r["unlimited"] > SAFE_MAX),
        "scanned": max((r["scanned"] for r in rated), default=""),
    }


def collect(api: str, key: str | None, sites: list[str], out: Path) -> None:
    done = {row["site"] for row in load(out)}
    todo = [s for s in sites if s not in done]
    say(f"{len(sites)} pages on the list, {len(done)} already saved, {len(todo)} to scan through {api}")
    out.parent.mkdir(parents=True, exist_ok=True)
    kept = 0
    with httpx.Client(timeout=240) as client, out.open("a", encoding="utf-8") as f:
        for site in todo:
            try:
                reply = client.post(
                    f"{api}/scan", json={"url": site}, headers={"X-API-Key": key} if key else {}
                )
            except httpx.HTTPError as err:
                say(f"  no answer for {site} ({type(err).__name__})")
                continue
            if reply.status_code == 429:
                say("The scan server's hourly limit is used up. Run again later, or set LINKLENS_API_KEY.")
                break
            if reply.status_code != 200:
                say(f"  the scan server answered {reply.status_code} for {site}")
                continue
            row = row_from_scan(site, reply.json())
            if row is None:
                say(f"  page not captured: {site}")
                continue
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
            f.flush()
            kept += 1
    say(f"Saved {kept} more {'page' if kept == 1 else 'pages'} to {out}")


def report(rows: list[dict]) -> None:
    model = page_model.load()
    if model is None:
        raise SystemExit("No model to check (api/app/ml/model.json is missing or doesn't fit the code).")
    rated = sorted(rate(rows, model), key=lambda r: -r["probability"])
    for r in rated:
        mark = "trusted" if r["trusted"] else ""
        say(
            f"{r['probability']:6.1%}  score {r['score']:3d}  rules {r['rule_score']:3d}"
            f"  {r['tags']:5d} tags  {mark:8s} {r['site']}"
        )
    s = summary(rated)
    say(
        f"\n{s['pages']} honest pages: {s['at_60']} rated 60% or more likely scam by the model"
        f" ({s['small_at_60']} of them under {SMALL_PAGE} tags), {s['at_95']} rated 95% or more."
    )
    say(
        f"Above Safe in a scan: {s['above_safe']}."
        f" If the model always counted in full: {s['unlimited_above_safe']}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=["collect", "report"])
    parser.add_argument("--api", default=os.environ.get("LINKLENS_API", "http://api:8000"))
    parser.add_argument("--sites", default=str(SITES))
    parser.add_argument("--file", default=os.environ.get("FEATURES_DIR", "/data/ml") + "/honest-sites.jsonl")
    args = parser.parse_args()
    if args.step == "collect":
        collect(
            args.api.rstrip("/"),
            os.environ.get("LINKLENS_API_KEY"),
            read_list(Path(args.sites)),
            Path(args.file),
        )
    else:
        report(load(Path(args.file)))


if __name__ == "__main__":
    main()

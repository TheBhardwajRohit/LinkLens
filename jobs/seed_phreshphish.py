"""Load a slice of the PhreshPhish research dataset into the page library.

PhreshPhish (CC BY 4.0, https://huggingface.co/datasets/phreshphish/phreshphish) holds about
666,000 pages, each with its link, HTML, a phish/benign label, the brand it targets, and a date.
This job streams rows straight from Hugging Face, so the 36 GB dataset is never saved to disk.
For every page it keeps only:

  - fingerprints and a few facts  -> the `pages` table (families are built from these)
  - the feature numbers           -> Parquet part files (the model is trained from these)

The HTML itself is thrown away. Run it in Docker or on GitHub Actions, never directly on Windows,
where the antivirus may quarantine phishing HTML mid-download.

    python -m jobs.seed_phreshphish --split train --limit 40000

A run that stops halfway can be continued with --skip: finished part files stay on disk and rows
already in the database are simply written again.
"""

import argparse
import multiprocessing
import os
from collections.abc import Iterator
from datetime import UTC, date, datetime
from itertools import islice
from pathlib import Path

from app import pages
from app.analysis.brands import display_brand
from app.analysis.toplist import toplist
from app.library import digest_page
from app.ml.features import NAMES
from jobs.common import connect, now, say

DATASET = "phreshphish/phreshphish"
SOURCE = "phreshphish"
MIN_HTML = 200
MAX_HTML = 2_000_000
# Rows are handed to the workers a window at a time, so only this many pages (a few hundred kB
# each) are ever in memory, however large --limit is.
WINDOW = 96
# A feature part file is written after this many rows, so a crash loses little.
PART_ROWS = WINDOW * 32
# Workers are replaced after this many pages, which keeps their memory from creeping up.
PAGES_PER_WORKER = 400
# Rows decoded at once. Each dataset file stores thousands of pages in one block of up to 2.6 GB,
# so the files are read directly with pyarrow in small batches. (The `datasets` library decoded
# whole blocks and, with forked workers on top, ran an 8 GB machine out of memory.)
READ_ROWS = 32
COLUMNS = ["sha256", "url", "label", "target", "date", "html"]


def _work(row: dict) -> dict | None:
    """Runs in a worker process: read one page into a `pages` row plus its feature numbers."""
    html, url = row.get("html") or "", row.get("url") or ""
    if len(html) < MIN_HTML or not url.startswith(("http://", "https://")):
        return None
    try:
        d = digest_page(url, html)
    except Exception:
        return None
    if not (d.prints.tlsh or d.prints.dom_hash):
        return None
    phish = row.get("label") == "phish"
    brand = display_brand(row.get("target")) if phish else None
    seen = row.get("date")
    if isinstance(seen, date) and not isinstance(seen, datetime):
        seen = datetime(seen.year, seen.month, seen.day, tzinfo=UTC)
    page = pages.page_row(
        source=SOURCE,
        source_ref=str(row.get("sha256"))[:40],
        url=url,
        fp=d.prints,
        site=d.link.site or d.link.registered_domain or d.link.host,
        label="phish" if phish else "benign",
        brand=brand or (d.impersonated[0] if phish and d.impersonated else None),
        scam_type=d.scam.id if phish and d.scam else None,
        title=d.page.title,
        seen_at=seen if isinstance(seen, datetime) else None,
    )
    return {
        "page": page,
        "features": d.features,
        "rule_score": d.rule_score,
        "label": int(phish),
        "date": str(row.get("date") or ""),
    }


def _init_worker() -> None:
    toplist.load()  # so "popular site" is judged the same way as in a live scan


def _slim(row: dict) -> dict:
    """Only what a worker needs, with oversized pages cut to the same limit a live scan uses."""
    return {
        "sha256": row.get("sha256"),
        "url": row.get("url"),
        "label": row.get("label"),
        "target": row.get("target"),
        "date": row.get("date"),
        "html": (row.get("html") or "")[:MAX_HTML],
    }


def read_rows(split: str, skip: int = 0) -> Iterator[dict]:
    """Rows of one split, in the dataset's own order, streamed straight from Hugging Face.
    Whole files are skipped by their row counts (read from the file footer, no download)."""
    import pyarrow.parquet as pq
    from huggingface_hub import HfFileSystem

    fs = HfFileSystem()
    files = sorted(fs.glob(f"datasets/{DATASET}/data/{split}-*.parquet"))
    if not files:
        raise RuntimeError(f"No {split} files found in {DATASET}")
    for path in files:
        with fs.open(path, "rb", block_size=8 * 1024 * 1024) as f:
            parquet = pq.ParquetFile(f, pre_buffer=False)
            rows_here = parquet.metadata.num_rows
            if skip >= rows_here:
                skip -= rows_here
                continue
            for batch in parquet.iter_batches(batch_size=READ_ROWS, columns=COLUMNS):
                if skip >= batch.num_rows:
                    skip -= batch.num_rows
                    continue
                rows = batch.to_pylist()
                yield from rows[skip:]
                skip = 0


def write_features(path: Path, records: list[dict]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    columns = {
        "id": [r["page"]["source_ref"] for r in records],
        "label": [r["label"] for r in records],
        "date": [r["date"] for r in records],
        "brand": [r["page"]["brand"] for r in records],
        "site": [r["page"]["site"] for r in records],
        # What the plain rules score this page from the link and HTML alone, to compare with the model.
        "rule_score": pa.array([r["rule_score"] for r in records], type=pa.int16()),
    }
    for i, name in enumerate(NAMES):
        columns[name] = pa.array([r["features"][i] for r in records], type=pa.float32())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    pq.write_table(pa.table(columns), tmp, compression="zstd")
    os.replace(tmp, path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--split", choices=["train", "test"], default="train")
    parser.add_argument("--limit", type=int, default=40_000, help="how many dataset rows to read")
    parser.add_argument("--skip", type=int, default=0, help="rows to skip first")
    parser.add_argument("--workers", type=int, default=min(max((os.cpu_count() or 2) - 2, 1), 5))
    parser.add_argument("--features-dir", default=os.environ.get("FEATURES_DIR", "/data/ml"))
    parser.add_argument("--no-database", action="store_true", help="only write the feature files")
    args = parser.parse_args()

    started = now()
    conn = None if args.no_database else connect()
    say(
        f"PhreshPhish {args.split}: reading {args.limit:,} rows from row {args.skip:,} with",
        f"{args.workers} workers;",
        "storing fingerprints" if conn else "no database, feature files only",
    )

    parts = Path(args.features_dir) / f"phreshphish-{args.split}"
    if args.skip == 0 and parts.exists():
        for old in parts.glob("part-*.parquet"):
            old.unlink()

    rows = read_rows(args.split, args.skip)

    pending: list[dict] = []
    read = skipped = kept_total = phish = 0
    part_start = args.skip

    def flush() -> None:
        nonlocal pending, part_start
        if pending:
            write_features(parts / f"part-{part_start:07d}.parquet", pending)
        part_start = args.skip + read
        pending = []

    # Workers start from a clean helper process (forkserver), not as copies of this one, so they
    # never hold on to the big blocks of rows this process is reading.
    workers = multiprocessing.get_context("forkserver")
    workers.set_forkserver_preload(["app.library"])
    with workers.Pool(args.workers, initializer=_init_worker, maxtasksperchild=PAGES_PER_WORKER) as pool:
        while read < args.limit:
            window = [_slim(r) for r in islice(rows, min(WINDOW, args.limit - read))]
            if not window:
                break
            results = pool.map(_work, window, chunksize=1)
            read += len(window)
            kept = [r for r in results if r is not None]
            skipped += len(window) - len(kept)
            kept_total += len(kept)
            phish += sum(r["label"] for r in kept)
            pending += kept
            if conn and kept:
                pages.save_many(conn, [r["page"] for r in kept])
            if read % PART_ROWS == 0:
                flush()
                rate = read / max((now() - started).total_seconds(), 1)
                done = args.skip + read
                say(f"  {done:,} read, {kept_total:,} kept, {skipped:,} skipped ({rate:.0f} pages/s)")
    flush()

    note = f"{args.split}: {phish:,} phish, {kept_total - phish:,} benign, {skipped:,} skipped"
    say(f"Done. {note}. Features: {parts}")
    if conn:
        pages.record_run(
            conn, SOURCE, started, ok=True, fetched=read, added=kept_total, failed=skipped, note=note
        )
        conn.close()


if __name__ == "__main__":
    main()

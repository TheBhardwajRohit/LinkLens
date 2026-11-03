"""Compare LinkLens with VirusTotal and PhishTank on the same links, for the website's comparison
page (web/compare/, data in web/src/compare/runs/).

Three steps. The lookups never open a page, so they can run anywhere. The scan step sends links to
a scan server, whose sandbox opens them: harmless links can go to the local one, live scam links
only to a scan server in an isolated place (safety rule 10: GitHub Actions, never Rohit's PC).

    python -m jobs.compare lists --in links.txt --out lists.json     (VIRUSTOTAL_API_KEY)
    python -m jobs.compare scan --in links.txt --api http://api:8000 --out scans.json --shots DIR
    python -m jobs.compare merge --lists lists.json --scans scans.json --out run.json

The lists are asked first, so they get the earliest look. VirusTotal is asked twice: what it
already knew, then a fresh analysis by all its engines. VirusTotal adds every link it is sent to
its public dataset, so only public links go to it (test pages, links from a public-domain feed),
with personal data redacted first. PhishTank is asked through its public check-URL lookup, which
needs no key; LinkLens itself never uses PhishTank. OpenPhish is not asked: its terms forbid
showing its data to anyone.

Run `lists` again a day later (`--out later.json`, then `merge --later later.json`) to see whether
the lists caught up.
"""

import argparse
import base64
import io
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.compare import vt_summary  # the same reading the scanner's live comparison uses
from app.redact import redact_url
from jobs.common import now, say

VT = "https://www.virustotal.com/api/v3"
VT_GAP_S = 15.5  # the free key allows 4 requests a minute
VT_POLLS = 4
PHISHTANK = "https://checkurl.phishtank.com/checkurl/"
# PhishTank asks for a User-Agent that names the application.
PHISHTANK_AGENT = "phishtank/linklens-compare"
SHOT_WIDTH = 640


def read_links(path: Path) -> list[dict]:
    """One link per line, optionally followed by " | a short note". Lines starting with # are skipped."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        url, _, note = (part.strip() for part in line.partition("|"))
        out.append({"url": url, "note": note or None})
    return out


def iso(seconds: int | None) -> str | None:
    return datetime.fromtimestamp(seconds, UTC).isoformat() if seconds else None


def vt_id(url: str) -> str:
    return base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")


class VirusTotal:
    """The free API, one request at a time, spaced out to stay inside its limit."""

    def __init__(self, key: str, client: httpx.Client):
        self.key = key
        self.client = client
        self.last = 0.0

    def call(self, method: str, path: str, **kwargs) -> httpx.Response:
        wait = self.last + VT_GAP_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.last = time.monotonic()
        return self.client.request(method, VT + path, headers={"x-apikey": self.key}, timeout=30, **kwargs)

    def report(self, url: str) -> dict:
        resp = self.call("GET", f"/urls/{vt_id(url)}")
        if resp.status_code == 404:
            return {"known": False}
        resp.raise_for_status()
        return vt_summary((resp.json().get("data") or {}).get("attributes") or {})

    def submit(self, url: str) -> tuple[str | None, str | None]:
        """The analysis id, or VirusTotal's reason for refusing the link."""
        resp = self.call("POST", "/urls", data={"url": url})
        if resp.status_code == 400:
            return None, (resp.json().get("error") or {}).get("message") or "VirusTotal refused the link."
        resp.raise_for_status()
        return (resp.json().get("data") or {}).get("id"), None

    def finished(self, analysis_id: str) -> bool:
        resp = self.call("GET", f"/analyses/{analysis_id}")
        resp.raise_for_status()
        return ((resp.json().get("data") or {}).get("attributes") or {}).get("status") == "completed"


def phishtank(url: str, client: httpx.Client) -> dict:
    try:
        resp = client.post(
            PHISHTANK,
            data={"url": url, "format": "json"},
            headers={"User-Agent": PHISHTANK_AGENT},
            timeout=30,
        )
        if resp.status_code == 509:
            return {"status": "limit"}
        resp.raise_for_status()
        r = resp.json().get("results") or {}
    except (httpx.HTTPError, ValueError) as e:
        return {"status": "error", "note": type(e).__name__}
    return {
        "status": "listed" if r.get("in_database") else "not_listed",
        "phish_id": r.get("phish_id"),
        "verified": bool(r.get("verified")),
        "verified_at": r.get("verified_at"),
        "valid": bool(r.get("valid")),
    }


def lists(args: argparse.Namespace) -> None:
    key = os.environ.get("VIRUSTOTAL_API_KEY", "")
    if not key:
        raise SystemExit("Set VIRUSTOTAL_API_KEY first.")
    links = read_links(Path(args.inp))
    rows = [{"url": redact_url(link["url"]), "asked_at": now().isoformat()} for link in links]
    with httpx.Client() as client:
        vt = VirusTotal(key, client)
        for row in rows:
            row["phishtank"] = phishtank(row["url"], client)
            row["vt_before"] = vt.report(row["url"])
            say(
                row["url"],
                "| PhishTank:",
                row["phishtank"]["status"],
                "| VirusTotal knew it:",
                row["vt_before"]["known"],
            )
        if args.submit:
            for row in rows:
                row["vt_analysis"], refused = vt.submit(row["url"])
                if refused:
                    row["vt_after"] = row["vt_before"] | {"refused": refused}
                    say(row["url"], "| VirusTotal refused it:", refused)
            for row in rows:
                analysis = row.pop("vt_analysis")
                if "vt_after" in row:
                    continue
                done = False
                for _ in range(VT_POLLS):
                    if analysis and vt.finished(analysis):
                        done = True
                        break
                row["vt_after"] = vt.report(row["url"]) | {"complete": done}
                s = row["vt_after"].get("stats") or {}
                now_says = f"{s.get('malicious', 0)} malicious, {s.get('suspicious', 0)} suspicious"
                say(row["url"], "| VirusTotal now:", now_says)
    Path(args.out).write_text(
        json.dumps({"asked_at": rows[0]["asked_at"] if rows else None, "links": rows}, indent=1),
        encoding="utf-8",
    )
    say(f"Saved {len(rows)} lookups to {args.out}")


def own_score(analysis: dict) -> int:
    """The score from LinkLens's own checks alone, leaving out what other services' lists added."""
    parts = (analysis.get("reasons") or []) + (analysis.get("good_signs") or [])
    return max(0, min(100, sum(r["points"] for r in parts if r.get("area") != "blacklist")))


def slug(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", url.lower().split("://", 1)[-1]).strip("-")[:60]


def save_shot(b64: str | None, path: Path) -> bool:
    if not b64:
        return False
    from PIL import Image

    image = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    if image.width > SHOT_WIDTH:
        image = image.resize((SHOT_WIDTH, round(image.height * SHOT_WIDTH / image.width)))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=72, optimize=True)
    return True


def trim(scan: dict) -> dict:
    """The parts of a LinkLens report the page shows. Links come redacted from the scan server."""
    analysis = scan.get("analysis") or {}
    visit = scan.get("visit") or {}
    recon = scan.get("recon") or {}
    reg = recon.get("registration") or {}
    server = recon.get("server") or {}
    certs = recon.get("cert_history") or {}
    family = scan.get("family") or {}
    siblings = scan.get("siblings") or {}
    link = analysis.get("link") or {}
    return {
        "id": scan.get("id"),
        "scanned_at": scan.get("created_at"),
        "score": analysis.get("score"),
        "own_score": own_score(analysis),
        "verdict": analysis.get("verdict"),
        "summary": analysis.get("summary"),
        "scam_type": analysis.get("scam_type"),
        "partial": analysis.get("partial"),
        "reasons": [{k: r.get(k) for k in ("text", "points", "area")} for r in analysis.get("reasons") or []],
        "good_signs": [
            {k: r.get(k) for k in ("text", "points", "area")} for r in analysis.get("good_signs") or []
        ],
        "model": (analysis.get("model") or {}).get("probability"),
        "unicode_host": link.get("unicode_host"),
        "lookalike": link.get("lookalike"),
        "visit": {
            "final_url": visit.get("final_url"),
            "title": visit.get("title"),
            "stopped": visit.get("stopped"),
            "notes": visit.get("notes") or [],
            "hops": len(visit.get("hops") or []),
            "blocked": visit.get("blocked") or [],
            "downloads": len(visit.get("downloads") or []),
            "bot_check": visit.get("bot_check"),
        },
        "owner": {
            "registrar": reg.get("registrar"),
            "created": reg.get("created"),
            "age_days": reg.get("age_days"),
            "country": server.get("country"),
            "network": server.get("as_org"),
            "abuse_email": server.get("abuse_email"),
            "certs_first_seen": certs.get("first_seen"),
            "cert_count": certs.get("cert_count"),
        },
        "lists": [
            {k: s.get(k) for k in ("id", "name", "status", "note")}
            for s in (scan.get("blacklists") or {}).get("sources") or []
        ],
        "family": {k: family.get(k) for k in ("status", "note", "copied_site", "library_size")}
        | {"name": (family.get("family") or {}).get("label")},
        "siblings": {
            tab: (siblings.get(tab) or {}).get("total", 0)
            for tab in ("same_server", "same_owner", "same_design", "lookalikes")
        },
    }


def scan(args: argparse.Namespace) -> None:
    links = read_links(Path(args.inp))
    shots = Path(args.shots) if args.shots else None
    headers = {"X-API-Key": os.environ["LINKLENS_API_KEY"]} if os.environ.get("LINKLENS_API_KEY") else {}
    rows = []
    with httpx.Client(timeout=200) as client:
        for i, link in enumerate(links):
            if i and args.gap:
                time.sleep(args.gap)  # room for the scan server's own VirusTotal checks
            resp = client.post(f"{args.api}/scan", json={"url": link["url"]}, headers=headers)
            if resp.status_code != 200:
                say(link["url"], "| scan failed:", resp.status_code, resp.text[:200])
                rows.append({"url": redact_url(link["url"]), "error": resp.status_code})
                continue
            report = resp.json()
            row = {"url": redact_url(link["url"]), "linklens": trim(report)}
            if shots and save_shot(
                (report.get("visit") or {}).get("screenshot_jpeg_b64"), shots / f"{slug(link['url'])}.jpg"
            ):
                row["shot"] = f"{slug(link['url'])}.jpg"
            rows.append(row)
            say(
                link["url"],
                "|",
                row["linklens"]["verdict"],
                row["linklens"]["score"],
                f"(own checks: {row['linklens']['own_score']})",
            )
    Path(args.out).write_text(json.dumps({"links": rows}, indent=1), encoding="utf-8")
    say(f"Saved {len(rows)} scans to {args.out}")


def merge(args: argparse.Namespace) -> None:
    def load(path: str | None) -> dict:
        return json.loads(Path(path).read_text(encoding="utf-8")) if path else {"links": []}

    asked = load(args.lists)
    scans = {row["url"]: row for row in load(args.scans)["links"]}
    later = {row["url"]: row for row in load(args.later)["links"]}
    notes = {redact_url(link["url"]): link["note"] for link in read_links(Path(args.inp))} if args.inp else {}
    rows = []
    for row in asked["links"]:
        url = row["url"]
        merged = row | (scans.get(url) or {})
        merged["note"] = notes.get(url)
        if url in later:
            merged["later"] = {k: later[url].get(k) for k in ("asked_at", "phishtank", "vt_before")}
        rows.append(merged)
    out = {"name": args.name, "made": now().isoformat(), "asked_at": asked.get("asked_at"), "links": rows}
    Path(args.out).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    say(f"Merged {len(rows)} links into {args.out}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    steps = parser.add_subparsers(dest="step", required=True)
    p = steps.add_parser("lists", help="ask VirusTotal and PhishTank about each link")
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out", required=True)
    p.add_argument(
        "--no-submit",
        dest="submit",
        action="store_false",
        help="only look up, don't ask VirusTotal for a fresh analysis",
    )
    p.set_defaults(run=lists)
    p = steps.add_parser("scan", help="scan each link with a LinkLens scan server")
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--api", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--shots", help="folder for small screenshots")
    p.add_argument("--gap", type=float, default=0, help="seconds to wait between scans")
    p.set_defaults(run=scan)
    p = steps.add_parser("merge", help="combine the lookups and the scans into one file for the page")
    p.add_argument("--lists", required=True)
    p.add_argument("--scans")
    p.add_argument("--later")
    p.add_argument("--in", dest="inp", help="the links file, for its notes")
    p.add_argument("--name", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(run=merge)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()

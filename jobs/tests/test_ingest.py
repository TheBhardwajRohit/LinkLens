"""Feed ingestion, tested without the internet, a sandbox, or a database. The "visits" here are
made-up results shaped like the sandbox's; no real scam link is ever opened by a test."""

import argparse
import base64
import io
import json
import random

from PIL import Image, ImageDraw

from jobs import ingest


def screenshot() -> str:
    image = Image.new("RGB", (640, 400), (20, 60, 120))
    ImageDraw.Draw(image).rectangle([50, 50, 400, 300], fill=(240, 240, 240))
    out = io.BytesIO()
    image.save(out, "JPEG")
    return base64.b64encode(out.getvalue()).decode()


def fake_visit(url: str, **changes) -> dict:
    rows = "".join(f"<tr><td>Field {i}</td><td>Please confirm item {i}</td></tr>" for i in range(30))
    html = (
        "<html><head><title>State Bank of India: KYC update</title></head><body>"
        "<h1>Update your KYC immediately</h1><form action='https://collector.example.net/x' method='post'>"
        "<input name='username'><input type='password' name='password'><input name='otp' placeholder='OTP'>"
        f"</form><table>{rows}</table><a href='https://other.example.org/'>help</a></body></html>"
    )
    visit = {
        "requested_url": url,
        "final_url": url,
        "title": "State Bank of India: KYC update",
        "status": 200,
        "hops": [{"url": url, "kind": "start", "status": 200, "blocked": False}],
        "html": html,
        "screenshot_jpeg_b64": screenshot(),
        "favicon_b64": base64.b64encode(b"icon").decode(),
        "server_ips": {"sbi-kyc.example.com": "93.184.215.14"},
        "headers": {"server": "nginx"},
        "tls": None,
        "stopped": None,
        "bot_check": None,
        "downloads": [],
    }
    visit.update(changes)
    return visit


def test_feed_links_are_cleaned_like_pasted_links():
    text = "\n".join(
        [
            "# comment",
            "http://bad.example.com/login.php",
            "hxxps://defanged[.]example.com/a",
            "http://127.0.0.1/admin",
            "http://192.168.1.10/router",
            "ftp://files.example.com/x",
            "javascript:alert(1)",
            "http://bad.example.com/login.php",
            "x" * 3000,
        ]
    )
    assert ingest.clean_links(text) == ["http://bad.example.com/login.php", "https://defanged.example.com/a"]


def test_choose_takes_new_links_first_skips_seen_ones_and_one_per_site():
    new = ["http://a.example.com/1", "http://a.example.com/2", "http://b.example.net/1"]
    backlog = [f"http://site{i}.example.org/x" for i in range(50)] + ["http://c.example.info/x"]
    seen = {ingest.url_hash("http://b.example.net/1")}
    picked = ingest.choose(new, backlog, seen, 3, random.Random(1))
    assert picked[0] == "http://a.example.com/1"
    assert "http://a.example.com/2" not in picked  # same site as the first
    assert "http://b.example.net/1" not in picked  # already seen
    # Picked links are marked as seen, so the next run won't take them again.
    assert all(ingest.url_hash(u) in seen for u in picked)
    # The second link on the same site waits for the next run.
    assert ingest.choose(new, [], seen, 5, random.Random(1)) == ["http://a.example.com/2"]
    assert ingest.choose(new, [], seen, 5, random.Random(1)) == []


def test_only_named_feeds_are_used(monkeypatch):
    monkeypatch.delenv("FEEDS", raising=False)
    assert ingest.enabled_feeds() == ["phishing_database"]  # OpenPhish is off unless asked for
    monkeypatch.setenv("FEEDS", "phishing_database, openphish, made_up")
    assert ingest.enabled_feeds() == ["phishing_database", "openphish"]


def test_summary_keeps_fingerprints_and_drops_the_page_itself():
    job = {"url": "https://sbi-kyc.example.com/login?email=victim@example.com", "source": "phishing_database"}
    record = ingest.summarize_visit(job, fake_visit(job["url"]))
    assert record["alive"] is True
    assert record["prints"]["tlsh"] and record["prints"]["dom_hash"] and record["prints"]["phash"]
    assert record["prints"]["favicon_hash"] is not None
    assert record["brand"] == "SBI" and record["scam_type"] == "banking"
    assert record["thumb_b64"]
    text = json.dumps(record)
    assert "<form" not in text and "html" not in record and "screenshot_jpeg_b64" not in record
    assert "victim@example.com" not in text  # personal data is removed before anything is passed on


def test_dead_pages_are_recognized():
    job = {"url": "https://gone.example.com/", "source": "phishing_database"}

    def alive(**changes) -> bool:
        return ingest.summarize_visit(job, fake_visit(job["url"], **changes))["alive"]

    assert alive() is True
    assert alive(stopped="unreachable", html=None) is False
    assert alive(status=404) is False
    assert alive(title="Account Suspended") is False
    assert alive(bot_check="Cloudflare challenge") is False
    assert alive(html="<p>hi</p>") is False


def test_plan_without_a_database_does_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    out = tmp_path / "urls.json"
    ingest.plan(argparse.Namespace(out=str(out), max=20, dry_run=False))
    assert json.loads(out.read_text()) == []
    assert "nowhere to store" in capsys.readouterr().out


def test_plan_dry_run_picks_links_from_the_feed(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("FEEDS", raising=False)
    lists = {
        ingest.FEEDS["phishing_database"]["new"]: "http://new.example.com/a\n",
        ingest.FEEDS["phishing_database"]["active"]: "\n".join(
            f"http://s{i}.example{i}.org/x" for i in range(30)
        ),
    }
    monkeypatch.setattr(ingest, "_download", lambda url: lists[url])
    out = tmp_path / "urls.json"
    ingest.plan(argparse.Namespace(out=str(out), max=4, dry_run=True))
    planned = json.loads(out.read_text())
    assert len(planned) == 4
    assert planned[0] == {"url": "http://new.example.com/a", "source": "phishing_database"}


def test_store_dry_run_builds_rows_without_a_database(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("MAXMIND_ACCOUNT_ID", raising=False)

    async def no_recon(visit, url):
        raise RuntimeError("no network in tests")

    monkeypatch.setattr(ingest.recon, "run_recon", no_recon)
    job = {"url": "https://sbi-kyc.example.com/login", "source": "phishing_database"}
    live = ingest.summarize_visit(job, fake_visit(job["url"]))
    dead = ingest.summarize_visit(job, fake_visit(job["url"], status=404))
    path = tmp_path / "pages.jsonl"
    path.write_text(json.dumps(live) + "\n" + json.dumps(dead) + "\n", encoding="utf-8")
    ingest.store(argparse.Namespace(inp=str(path)))
    out = capsys.readouterr().out
    assert "Would store 1 live pages, 1 gone or blocked" in out
    assert "brand=SBI" in out

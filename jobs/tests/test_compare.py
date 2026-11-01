"""The comparison job's own logic, with VirusTotal and PhishTank replaced by fakes (no network)."""

import argparse
import json

import httpx

from jobs import compare


def test_reads_links_with_notes_and_skips_comments(tmp_path):
    path = tmp_path / "links.txt"
    path.write_text(
        "# a comment\n\nhttps://example.com/ | a safe page\nhttp://localtest.me/\n", encoding="utf-8"
    )
    assert compare.read_links(path) == [
        {"url": "https://example.com/", "note": "a safe page"},
        {"url": "http://localtest.me/", "note": None},
    ]


def test_virustotal_summary_lists_flags_and_redacts():
    attrs = {
        "last_analysis_results": {
            "Zeta": {"category": "suspicious", "result": "suspicious"},
            "Beta": {"category": "malicious", "result": "phishing"},
            "Alpha": {"category": "harmless", "result": "clean"},
        },
        "last_analysis_stats": {"malicious": 1, "suspicious": 1, "harmless": 1},
        "categories": {"a": "phishing", "b": "phishing"},
        "reputation": -12,
        "last_final_url": "https://x.example/login?email=me@x.example",
        "first_submission_date": 0,
    }
    s = compare.vt_summary(attrs)
    assert s["engines"] == 3
    assert [f["engine"] for f in s["flagged"]] == ["Beta", "Zeta"]  # malicious first
    assert s["categories"] == ["phishing"]
    assert "me@x.example" not in s["final_url"]
    assert s["first_seen"] is None


def test_own_score_leaves_out_other_services_lists():
    analysis = {
        "reasons": [
            {"text": "listed", "points": 70, "area": "blacklist"},
            {"text": "lookalike", "points": 45, "area": "link"},
        ],
        "good_signs": [{"text": "old", "points": -10, "area": "domain"}],
    }
    assert compare.own_score(analysis) == 35
    assert (
        compare.own_score({"reasons": [], "good_signs": [{"text": "x", "points": -40, "area": "reputation"}]})
        == 0
    )


def test_trim_keeps_what_the_page_shows():
    scan = {
        "id": "s1",
        "analysis": {
            "score": 47,
            "verdict": "suspicious",
            "reasons": [{"text": "sbi", "points": 30, "area": "link"}],
            "good_signs": [],
            "link": {"unicode_host": None, "lookalike": {"brand": "SBI"}},
        },
        "visit": {"final_url": None, "stopped": "unreachable", "hops": [{}], "screenshot_jpeg_b64": "big"},
        "family": {"status": "skipped", "family": {"label": "SBI YONO"}},
    }
    row = compare.trim(scan)
    assert row["verdict"] == "suspicious" and row["own_score"] == 30
    assert row["visit"]["hops"] == 1 and "screenshot_jpeg_b64" not in json.dumps(row)
    assert row["family"]["name"] == "SBI YONO"


def fake_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_virustotal_refusal_is_a_result(monkeypatch):
    monkeypatch.setattr(compare, "VT_GAP_S", 0)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "Unable to canonicalize url"}})

    with fake_client(handler) as client:
        assert compare.VirusTotal("k", client).submit("http://x.example/") == (
            None,
            "Unable to canonicalize url",
        )


def test_phishtank_answers():
    answers = {
        "http://listed.example/": {"results": {"in_database": True, "phish_id": 7, "verified": False}},
        "http://clean.example/": {"results": {"in_database": False}},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"].startswith("phishtank/")
        url = dict(httpx.QueryParams(request.content.decode()))["url"]
        if url == "http://busy.example/":
            return httpx.Response(509)
        return httpx.Response(200, json=answers[url])

    with fake_client(handler) as client:
        assert compare.phishtank("http://listed.example/", client)["status"] == "listed"
        assert compare.phishtank("http://clean.example/", client)["status"] == "not_listed"
        assert compare.phishtank("http://busy.example/", client)["status"] == "limit"


def test_merge_joins_lookups_scans_and_a_later_check(tmp_path):
    url = "https://example.com/"
    (tmp_path / "lists.json").write_text(
        json.dumps({"asked_at": "t0", "links": [{"url": url, "asked_at": "t0"}]})
    )
    (tmp_path / "scans.json").write_text(json.dumps({"links": [{"url": url, "linklens": {"score": 0}}]}))
    (tmp_path / "later.json").write_text(
        json.dumps({"links": [{"url": url, "asked_at": "t1", "phishtank": {}, "vt_before": {}}]})
    )
    (tmp_path / "links.txt").write_text(f"{url} | safe\n")
    out = tmp_path / "run.json"
    compare.merge(
        argparse.Namespace(
            lists=str(tmp_path / "lists.json"),
            scans=str(tmp_path / "scans.json"),
            later=str(tmp_path / "later.json"),
            inp=str(tmp_path / "links.txt"),
            name="test",
            out=str(out),
        )
    )
    run = json.loads(out.read_text(encoding="utf-8"))
    row = run["links"][0]
    assert row["linklens"] == {"score": 0} and row["note"] == "safe" and row["later"]["asked_at"] == "t1"

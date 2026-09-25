"""Recon tests. Every source is replaced by saved sample replies or fakes: no network at all."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app import recon
from app.recon import ct, http_info, rdap, whois
from app.recon.domains import age_days, parse_date, registered_domain
from app.recon.geoip import GeoIP
from app.recon.models import CertHistory, DnsRecords, Registration, Server

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    text = (FIXTURES / name).read_text()
    return json.loads(text) if name.endswith(".json") else text


# --- domains ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("login.secure.paypal.co.uk", "paypal.co.uk"),
        ("www.example.com", "example.com"),
        ("sbi.co.in", "sbi.co.in"),
        ("a.b.c.github.io", "github.io"),
        ("93.184.215.14", None),
        ("[2606:4700::1111]", None),
        ("", None),
    ],
)
def test_registered_domain(host, expected):
    assert registered_domain(host) == expected


@pytest.mark.parametrize(
    "value",
    ["2026-09-01T12:00:00Z", "2026-09-01 12:00:00", "01-Sep-2026", "2026.09.01", "2026-09-01"],
)
def test_parse_date_formats(value):
    parsed = parse_date(value)
    assert (parsed.year, parsed.month, parsed.day) == (2026, 9, 1)


def test_age_days():
    now = datetime(2026, 9, 25, tzinfo=UTC)
    assert age_days(parse_date("2026-09-20T10:00:00Z"), now) == 4
    assert age_days(None) is None


# --- RDAP ------------------------------------------------------------------


def test_rdap_domain_parsing():
    reg = rdap.parse_domain("secure-login-example.com", load("rdap_domain.json"))
    assert reg.source == "rdap"
    assert reg.registrar == "Example Registrar, LLC"
    assert reg.registrar_abuse_email == "abuse@registrar.example"
    assert reg.registrant == "REDACTED FOR PRIVACY"
    assert reg.created.startswith("2026-09-20")
    assert reg.expires == "2027-09-20T10:00:00Z"
    assert reg.nameservers == ["ns1.cheap-dns.example", "ns2.cheap-dns.example"]
    assert "server hold" in reg.flags
    assert reg.dnssec is False


def test_rdap_ip_parsing_finds_nested_abuse_contact():
    server = rdap.parse_ip("203.0.113.7", load("rdap_ip.json"))
    assert server.abuse_email == "abuse@hosting.example"
    assert server.network_name == "BULLETPROOF-HOSTING-EXAMPLE"
    assert server.network_range == "203.0.113.0 - 203.0.113.255"
    assert server.country_code == "NL"


@pytest.fixture
def fake_bootstrap(monkeypatch):
    boot = {
        rdap.BOOTSTRAP["dns"]: {"services": [[["com", "net"], ["http://x/", "https://rdap.example/com/"]]]},
        rdap.BOOTSTRAP["ipv4"]: {
            "services": [
                [["203.0.0.0/8"], ["https://rdap.big.example/"]],
                [["203.0.113.0/24"], ["https://rdap.small.example/"]],
            ]
        },
    }

    async def fake_get_json(url, **kwargs):
        return boot[url]

    monkeypatch.setattr(rdap, "get_json", fake_get_json)
    rdap._bootstrap_cache._items.clear()


@pytest.mark.anyio
async def test_rdap_server_lookup_prefers_https_and_longest_prefix(fake_bootstrap):
    assert await rdap.domain_server("secure-login-example.com") == "https://rdap.example/com/"
    assert await rdap.domain_server("wallet-example.io") is None  # no RDAP: WHOIS is used instead
    assert await rdap.ip_server("203.0.113.9") == "https://rdap.small.example/"


# --- WHOIS -----------------------------------------------------------------


def test_whois_parsing():
    reg = whois.parse("wallet-example.io", load("whois_io.txt"))
    assert reg.source == "whois"
    assert reg.registrar == "Example Registrar, LLC"
    assert reg.created.startswith("2026-09-01")
    assert reg.expires.startswith("2027-09-01")
    assert reg.nameservers == ["ns1.parking.example", "ns2.parking.example"]


def test_whois_not_found():
    reg = whois.parse("nothing-here.io", "No match for domain NOTHING-HERE.IO\n")
    assert reg.status == "not_found"


# --- certificate history ---------------------------------------------------


def test_ct_summary():
    rows = load("crtsh.json")
    certs = [
        {"names": r["name_value"].split("\n"), "not_before": r["not_before"], "issuer": "x"} for r in rows
    ]
    h = ct.summarize("secure-login-example.com", certs, "crt.sh")
    assert h.subdomains == ["mail.secure-login-example.com", "www.secure-login-example.com"]
    assert h.other_domains == ["bank-example.co.uk", "verify-account-example.net"]
    assert h.first_seen == "2026-09-20T11:00:00"


@pytest.mark.anyio
async def test_ct_uses_crtsh_and_dedupes(monkeypatch):
    async def fake_get_json(url, **kwargs):
        assert url.startswith("https://crt.sh/")
        return load("crtsh.json")

    monkeypatch.setattr(ct, "get_json", fake_get_json)
    ct._cache._items.clear()
    h = await ct.history("secure-login-example.com")
    assert h.source == "crt.sh"
    assert h.cert_count == 3  # id 101 appears twice in the reply
    assert h.issuers[0] == "Let's Encrypt"


@pytest.mark.anyio
async def test_ct_falls_back_to_certspotter(monkeypatch):
    async def fake_get_json(url, **kwargs):
        if "crt.sh" in url:
            raise ConnectionError("502 Bad Gateway")
        return load("certspotter.json")

    monkeypatch.setattr(ct, "get_json", fake_get_json)
    ct._cache._items.clear()
    h = await ct.history("secure-login-example.com")
    assert h.source == "certspotter"
    assert "Current certificates only" in h.note


@pytest.mark.anyio
async def test_ct_reports_when_both_services_fail(monkeypatch):
    async def fake_get_json(url, **kwargs):
        raise ConnectionError("down")

    monkeypatch.setattr(ct, "get_json", fake_get_json)
    ct._cache._items.clear()
    h = await ct.history("secure-login-example.com")
    assert h.status == "error"


# --- DNS -------------------------------------------------------------------


@pytest.mark.anyio
async def test_dns_keeps_partial_results_when_one_lookup_stalls(monkeypatch):
    from app.recon import dns_records

    answers = {
        "A": ["93.184.215.14"],
        "AAAA": [],
        "CNAME": [],
        "MX": ["10 mail.example.com."],
        "NS": None,
        "TXT": [],
    }

    async def fake_query(resolver, name, rtype):
        return answers[rtype]

    monkeypatch.setattr(dns_records, "_query", fake_query)
    r = await dns_records.lookup("www.example.com", "example.com")
    assert r.status == "ok"
    assert r.a == ["93.184.215.14"]
    assert r.mx == ["mail.example.com"]
    assert "NS" in r.note


@pytest.mark.anyio
async def test_dns_tries_the_system_resolver_when_public_ones_fail(monkeypatch):
    from app.recon import dns_records

    used = []

    async def fake_all(resolver, host, zone):
        used.append(resolver)
        return [None] * 6 if len(used) == 1 else [["1.1.1.1"], [], [], [], [], []]

    monkeypatch.setattr(dns_records, "_all", fake_all)
    r = await dns_records.lookup("example.com", "example.com")
    assert len(used) == 2
    assert r.a == ["1.1.1.1"]


# --- HTTP headers ----------------------------------------------------------


def test_http_info_detects_hosting_and_missing_security_headers():
    info = http_info.analyze(
        {"Server": "cloudflare", "CF-RAY": "abc", "X-Powered-By": "PHP/8.3"},
        '<meta name="generator" content="WordPress 6.8"><link href="/wp-content/x.css">',
    )
    assert info.tech[:2] == ["Cloudflare", "PHP"]
    assert "WordPress" in info.tech
    assert info.generator == "WordPress 6.8"
    assert info.security_headers["HSTS"] is False


def test_http_info_skips_when_nothing_was_captured():
    assert http_info.analyze({}, None).status == "skipped"


# --- GeoIP -----------------------------------------------------------------


def test_geoip_without_databases_says_not_configured(tmp_path):
    assert GeoIP(tmp_path).lookup("8.8.8.8").status == "not_configured"


def test_geoip_lookup_fills_location_and_network(tmp_path):
    class Obj:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class City:
        def city(self, ip):
            return Obj(
                country=Obj(iso_code="NL", name="Netherlands"),
                city=Obj(name="Amsterdam"),
                location=Obj(latitude=52.37, longitude=4.89, accuracy_radius=20),
            )

    class Asn:
        def asn(self, ip):
            return Obj(autonomous_system_number=64500, autonomous_system_organization="Example Hosting")

    geo = GeoIP(tmp_path)
    geo._readers = {"GeoLite2-City": City(), "GeoLite2-ASN": Asn()}
    s = geo.lookup("203.0.113.7")
    assert (s.country, s.city, s.asn, s.as_org) == ("Netherlands", "Amsterdam", 64500, "Example Hosting")


# --- putting it together ---------------------------------------------------


@pytest.fixture
def fake_sources(monkeypatch):
    calls = {"ip": []}

    async def fake_registration(domain):
        return Registration(domain=domain, registrar="Example Registrar, LLC", age_days=5)

    async def fake_history(domain):
        return CertHistory(domain=domain, cert_count=2)

    async def fake_dns(host, domain):
        return DnsRecords(host=host, a=["10.0.0.5", "1.1.1.1"])

    async def fake_server(ip):
        calls["ip"].append(ip)
        return Server(ip=ip, country="Netherlands")

    monkeypatch.setattr(recon, "registration", fake_registration)
    monkeypatch.setattr(recon.ct, "history", fake_history)
    monkeypatch.setattr(recon.dns_records, "lookup", fake_dns)
    monkeypatch.setattr(recon, "server_info", fake_server)
    return calls


def visit(**kw):
    base = {
        "requested_url": "https://bit.example.com/x",
        "final_url": "https://login.secure-login-example.com/",
        "hops": [
            {"url": "https://short.link-example.com/x"},
            {"url": "https://login.secure-login-example.com/"},
        ],
        "server_ips": {"login.secure-login-example.com": "93.184.215.14"},
        "headers": {"server": "nginx"},
        "html": "<title>x</title>",
        "tls": {"issuer": "R11"},
    }
    base.update(kw)
    return base


@pytest.mark.anyio
async def test_recon_uses_the_ip_the_sandbox_connected_to(fake_sources):
    r = await recon.run_recon(visit(), "https://short.link-example.com/x")
    assert r.registered_domain == "secure-login-example.com"
    assert r.registration.registrar == "Example Registrar, LLC"
    assert fake_sources["ip"] == ["93.184.215.14"]
    assert [d.domain for d in r.chain_domains] == ["link-example.com"]
    assert r.certificate == {"issuer": "R11"}
    assert "nginx" in r.http.tech


@pytest.mark.anyio
async def test_recon_falls_back_to_first_public_dns_answer(fake_sources):
    await recon.run_recon(visit(server_ips={}), "https://x")
    assert fake_sources["ip"] == ["1.1.1.1"]  # 10.0.0.5 is private and skipped


@pytest.mark.anyio
async def test_recon_never_looks_up_private_addresses(fake_sources):
    r = await recon.run_recon(visit(final_url="http://10.1.2.3/", hops=[], server_ips={}), "http://10.1.2.3/")
    assert r.server.status == "skipped"
    assert fake_sources["ip"] == []


@pytest.mark.anyio
async def test_a_name_pointing_only_at_private_addresses_says_so(fake_sources, monkeypatch):
    async def private_dns(host, domain):
        return DnsRecords(host=host, a=["127.0.0.1"])

    monkeypatch.setattr(recon.dns_records, "lookup", private_dns)
    r = await recon.run_recon(visit(server_ips={}), "https://x")
    assert r.server.status == "skipped"
    assert "127.0.0.1" in r.server.note
    assert fake_sources["ip"] == []


@pytest.mark.anyio
async def test_slow_sources_time_out_with_a_plain_note():
    async def slow():
        await asyncio.sleep(5)

    result = await recon._timed(slow(), 0.05, Registration(domain="x.com"))
    assert result.status == "timeout"
    assert "didn't answer in time" in result.note

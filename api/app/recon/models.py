"""What recon found. Every part has a status, so the page can say plainly when a source
was slow, missing, or not set up, instead of failing silently."""

from typing import Literal

from pydantic import BaseModel

Status = Literal["ok", "not_found", "not_configured", "timeout", "error", "skipped"]


class Registration(BaseModel):
    domain: str
    status: Status = "ok"
    source: Literal["rdap", "whois"] | None = None
    registrar: str | None = None
    registrar_abuse_email: str | None = None
    registrant: str | None = None
    created: str | None = None  # ISO 8601
    updated: str | None = None
    expires: str | None = None
    age_days: int | None = None
    nameservers: list[str] = []
    flags: list[str] = []  # registry status codes, e.g. "client hold"
    dnssec: bool | None = None
    note: str | None = None


class DnsRecords(BaseModel):
    host: str
    status: Status = "ok"
    a: list[str] = []
    aaaa: list[str] = []
    cname: list[str] = []
    mx: list[str] = []
    ns: list[str] = []
    txt: list[str] = []
    note: str | None = None


class Server(BaseModel):
    ip: str | None = None
    status: Status = "ok"
    country_code: str | None = None
    country: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    accuracy_km: int | None = None
    asn: int | None = None
    as_org: str | None = None
    network_name: str | None = None
    network_range: str | None = None
    abuse_email: str | None = None
    note: str | None = None


class CertHistory(BaseModel):
    domain: str
    status: Status = "ok"
    source: Literal["crt.sh", "certspotter"] | None = None
    cert_count: int = 0
    first_seen: str | None = None
    latest: str | None = None
    issuers: list[str] = []
    subdomains: list[str] = []
    other_domains: list[str] = []
    note: str | None = None


class HttpInfo(BaseModel):
    status: Status = "ok"
    server: str | None = None
    powered_by: str | None = None
    generator: str | None = None
    tech: list[str] = []
    security_headers: dict[str, bool] = {}


class Recon(BaseModel):
    host: str | None = None
    registered_domain: str | None = None
    registration: Registration | None = None
    chain_domains: list[Registration] = []
    dns: DnsRecords | None = None
    server: Server | None = None
    certificate: dict | None = None  # captured by the sandbox (only it may contact the site)
    cert_history: CertHistory | None = None
    http: HttpInfo | None = None
    duration_ms: int = 0

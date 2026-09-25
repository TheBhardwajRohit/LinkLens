"""Read a site's TLS certificate. This contacts the target, so it lives in the sandbox and goes
through the same SSRF guard, connecting only to the exact IP the guard checked."""

import asyncio
import contextlib
import hashlib
import ssl
from datetime import UTC, datetime

from cryptography import x509
from cryptography.x509.oid import ExtensionOID, NameOID
from pydantic import BaseModel

from app.guard import Guard

TIMEOUT_S = 6


class TlsInfo(BaseModel):
    host: str
    protocol: str | None = None
    subject: str | None = None
    issuer: str | None = None
    issuer_org: str | None = None
    not_before: str | None = None
    not_after: str | None = None
    days_left: int | None = None
    names: list[str] = []
    serial: str | None = None
    sha256: str | None = None
    self_signed: bool = False
    trusted: bool = False
    problem: str | None = None  # why a normal browser would warn, in plain words


def _name(cert_name: x509.Name, oid) -> str | None:
    attrs = cert_name.get_attributes_for_oid(oid)
    return str(attrs[0].value) if attrs else None


def parse(host: str, der: bytes, protocol: str | None = None) -> TlsInfo:
    cert = x509.load_der_x509_certificate(der)
    names: list[str] = []
    with contextlib.suppress(x509.ExtensionNotFound):
        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        names = san.get_values_for_type(x509.DNSName)
    not_after = cert.not_valid_after_utc
    return TlsInfo(
        host=host,
        protocol=protocol,
        subject=_name(cert.subject, NameOID.COMMON_NAME),
        issuer=_name(cert.issuer, NameOID.COMMON_NAME),
        issuer_org=_name(cert.issuer, NameOID.ORGANIZATION_NAME),
        not_before=cert.not_valid_before_utc.isoformat(),
        not_after=not_after.isoformat(),
        days_left=(not_after - datetime.now(UTC)).days,
        names=names[:100],
        serial=format(cert.serial_number, "x"),
        sha256=hashlib.sha256(der).hexdigest(),
        self_signed=cert.issuer == cert.subject,
    )


async def _connect(ip: str, port: int, host: str, context: ssl.SSLContext):
    return await asyncio.wait_for(
        asyncio.open_connection(ip, port, ssl=context, server_hostname=host), TIMEOUT_S
    )


async def fetch(host: str, port: int, guard: Guard) -> TlsInfo:
    allowed = await guard.check(host, port)

    # First connection: accept any certificate, so we can read even a broken one.
    loose = ssl.create_default_context()
    loose.check_hostname = False
    loose.verify_mode = ssl.CERT_NONE
    _, writer = await _connect(allowed.ip, port, host, loose)
    try:
        sslobj = writer.get_extra_info("ssl_object")
        info = parse(host, sslobj.getpeercert(binary_form=True), sslobj.version())
    finally:
        writer.close()

    # Second connection: would a normal browser trust it?
    try:
        _, writer = await _connect(allowed.ip, port, host, ssl.create_default_context())
        writer.close()
        info.trusted = True
    except ssl.SSLCertVerificationError as err:
        info.problem = _plain(err.verify_message or str(err))
    except (ssl.SSLError, OSError, TimeoutError) as err:
        info.problem = f"The secure connection failed ({type(err).__name__})."
    return info


def _plain(message: str) -> str:
    m = message.lower()
    if "self-signed" in m or "self signed" in m:
        return "The certificate is self-signed, so no trusted authority vouches for it."
    if "expired" in m:
        return "The certificate has expired."
    if "hostname mismatch" in m or "doesn't match" in m or "not valid for" in m:
        return "The certificate is for a different name than this site."
    if "unable to get local issuer" in m:
        return "The certificate isn't signed by an authority browsers trust."
    return f"Browsers would show a warning: {message}"

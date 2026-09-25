// "Who's behind it": server, domain, and certificate facts from recon.
// Names from the scanned site are shown defanged, as plain text, like everywhere else in the report.

import { Check, CircleAlert, Globe, Lock, LockOpen, Server as ServerIcon, X, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import type { Recon } from "../lib/api";
import { daysSince, formatAge, formatDate, isRedacted, NEW_DOMAIN_DAYS } from "../lib/format";
import { CopyButton, Section } from "./ReportParts";

const defangName = (name: string) => name.replaceAll(".", "[.]");

function Card({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-white/[0.08] bg-ink/40 p-4">
      <p className="flex items-center gap-2 text-sm font-semibold text-cream">
        <Icon className="h-4 w-4 text-blue-400" aria-hidden="true" />
        {title}
      </p>
      <dl className="mt-3 space-y-2.5 text-sm">{children}</dl>
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 break-words text-slate-200">{children}</dd>
    </div>
  );
}

function Note({ children }: { children: ReactNode }) {
  return <p className="text-sm text-slate-400">{children}</p>;
}

function Warn({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-start gap-1.5 text-sm text-amber-300">
      <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </p>
  );
}

function Names({ names, limit = 4 }: { names: string[]; limit?: number }) {
  const shown = names.slice(0, limit);
  return (
    <span className="font-mono text-[13px]">
      {shown.map(defangName).join(", ")}
      {names.length > limit && <span className="font-sans text-slate-500"> and {names.length - limit} more</span>}
    </span>
  );
}

function ServerCard({ recon }: { recon: Recon }) {
  const s = recon.server;
  if (!s) return <Card icon={ServerIcon} title="Server"><Note>No server address was found.</Note></Card>;
  const place = [s.city, s.country].filter(Boolean).join(", ");
  return (
    <Card icon={ServerIcon} title="Server">
      {s.status !== "ok" && s.note && <Note>{s.note}</Note>}
      {place && (
        <Row label="Location">
          {place}
          {s.accuracy_km ? <span className="text-slate-500"> (roughly, within {s.accuracy_km} km)</span> : null}
        </Row>
      )}
      {s.ip && (
        <Row label="IP address">
          <span className="flex items-center gap-1 font-mono text-[13px]">
            {s.ip}
            <CopyButton text={s.ip} label="Copy the IP address" />
          </span>
        </Row>
      )}
      {(s.as_org || s.asn) && (
        <Row label="Hosting network">
          {s.as_org ?? "Unknown"}
          {s.asn ? <span className="text-slate-500"> (AS{s.asn})</span> : null}
        </Row>
      )}
      {s.network_name && <Row label="Network name">{s.network_name}</Row>}
      {s.abuse_email && (
        <Row label="Report abuse to">
          <span className="flex items-center gap-1">
            <span className="break-all">{s.abuse_email}</span>
            <CopyButton text={s.abuse_email} label="Copy the abuse email address" />
          </span>
        </Row>
      )}
    </Card>
  );
}

function DomainCard({ recon }: { recon: Recon }) {
  const r = recon.registration;
  if (!recon.registered_domain || !r) {
    return <Card icon={Globe} title="Domain"><Note>The link uses a bare IP address, so there's no domain to look up.</Note></Card>;
  }
  const isNew = r.age_days !== null && r.age_days < NEW_DOMAIN_DAYS;
  return (
    <Card icon={Globe} title="Domain">
      <Row label="Domain">
        <span className="font-mono text-[13px]">{defangName(r.domain)}</span>
      </Row>
      {r.status !== "ok" && r.note && <Note>{r.note}</Note>}
      {isNew && <Warn>Registered only {formatAge(r.age_days)} ago. Scam sites are often brand new.</Warn>}
      {r.created && (
        <Row label="Registered">
          {formatDate(r.created)}
          {r.age_days !== null && !isNew && <span className="text-slate-500"> ({formatAge(r.age_days)} ago)</span>}
        </Row>
      )}
      {r.expires && <Row label="Expires">{formatDate(r.expires)}</Row>}
      {r.registrar && <Row label="Registrar">{r.registrar}</Row>}
      {r.status === "ok" && (
        <Row label="Owner">
          {!r.registrant ? (
            <span className="text-slate-400">Not published by the registry</span>
          ) : isRedacted(r.registrant) ? (
            <span className="text-slate-400">Hidden for privacy</span>
          ) : (
            r.registrant
          )}
        </Row>
      )}
      {r.nameservers.length > 0 && (
        <Row label="Name servers">
          <Names names={r.nameservers} limit={3} />
        </Row>
      )}
      {r.flags.some((f) => /hold|suspend|inactive|redemption|pending delete/i.test(f)) && (
        <Warn>Registry status: {r.flags.filter((f) => /hold|suspend|inactive|redemption|pending/i.test(f)).join(", ")}</Warn>
      )}
      {recon.chain_domains.length > 0 && (
        <Row label="Other domains in the link trail">
          <ul className="space-y-0.5">
            {recon.chain_domains.map((d) => (
              <li key={d.domain}>
                <span className="font-mono text-[13px]">{defangName(d.domain)}</span>
                <span className="text-slate-500"> {d.age_days !== null ? `(${formatAge(d.age_days)} old)` : "(age unknown)"}</span>
              </li>
            ))}
          </ul>
        </Row>
      )}
      {r.source && <p className="text-xs text-slate-500">From {r.source === "rdap" ? "RDAP" : "WHOIS"}</p>}
    </Card>
  );
}

function CertificateCard({ recon, finalUrl }: { recon: Recon; finalUrl: string }) {
  const c = recon.certificate;
  const h = recon.cert_history;
  const https = finalUrl.startsWith("https:");
  return (
    <Card icon={https ? Lock : LockOpen} title="Certificate">
      {!c && (https ? <Note>No certificate was captured.</Note> : <Warn>No HTTPS. The page isn't encrypted.</Warn>)}
      {c && (
        <>
          {c.trusted ? (
            <p className="flex items-center gap-1.5 text-sm text-slate-200">
              <Check className="h-4 w-4 text-blue-400" aria-hidden="true" />
              Browsers trust it
            </p>
          ) : (
            <Warn>{c.problem ?? "Browsers would show a warning."}</Warn>
          )}
          <Row label="Issued by">{c.issuer_org ?? c.issuer ?? "Unknown"}</Row>
          {c.not_before && c.not_after && (
            <Row label="Valid">
              {formatDate(c.not_before)} to {formatDate(c.not_after)}
              {c.days_left !== null && (
                <span className="text-slate-500"> ({c.days_left < 0 ? "expired" : `${c.days_left} days left`})</span>
              )}
            </Row>
          )}
          {c.names.length > 0 && (
            <Row label={`Names on it (${c.names.length})`}>
              <Names names={c.names} />
            </Row>
          )}
        </>
      )}
      {h && h.status === "ok" && h.cert_count > 0 && (
        <Row label="Certificate history">
          {h.cert_count} {h.cert_count === 1 ? "certificate" : "certificates"}
          {h.first_seen && (
            <>
              , first on {formatDate(h.first_seen)}
              <span className="text-slate-500"> ({formatAge(daysSince(h.first_seen))} ago)</span>
            </>
          )}
        </Row>
      )}
      {h && h.other_domains.length > 0 && (
        <Row label="Shares certificates with">
          <Names names={h.other_domains} />
        </Row>
      )}
      {h && h.note && <p className="text-xs text-slate-500">{h.note}</p>}
    </Card>
  );
}

function DnsDetails({ recon }: { recon: Recon }) {
  const d = recon.dns;
  if (!d) return null;
  const rows: [string, string[]][] = [
    ["A (IPv4)", d.a],
    ["AAAA (IPv6)", d.aaaa],
    ["CNAME (alias)", d.cname.map(defangName)],
    ["MX (mail)", d.mx.map(defangName)],
    ["NS (name servers)", d.ns.map(defangName)],
    ["TXT", d.txt],
  ];
  return (
    <details className="rounded-xl border border-white/[0.08] bg-ink/30 px-4 py-3 text-sm">
      <summary className="cursor-pointer text-slate-300 hover:text-white">DNS records</summary>
      {d.note && <p className="mt-2 text-slate-400">{d.note}</p>}
      <dl className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-[10rem_1fr]">
        {rows.map(([label, values]) => (
          <div key={label} className="contents">
            <dt className="text-slate-500">{label}</dt>
            <dd className="whitespace-pre-line break-all font-mono text-[13px] text-slate-300">{values.length ? values.join("\n") : <span className="font-sans text-slate-600">none</span>}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

function TechDetails({ recon }: { recon: Recon }) {
  const h = recon.http;
  if (!h || h.status !== "ok") return null;
  return (
    <details className="rounded-xl border border-white/[0.08] bg-ink/30 px-4 py-3 text-sm">
      <summary className="cursor-pointer text-slate-300 hover:text-white">Server software and security headers</summary>
      <dl className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-[10rem_1fr]">
        {h.tech.length > 0 && (
          <div className="contents">
            <dt className="text-slate-500">Built with</dt>
            <dd className="flex flex-wrap gap-1.5">
              {h.tech.map((t) => (
                <span key={t} className="rounded-md bg-white/5 px-2 py-0.5 text-slate-200 ring-1 ring-white/10">
                  {t}
                </span>
              ))}
            </dd>
          </div>
        )}
        {h.server && (
          <div className="contents">
            <dt className="text-slate-500">Server header</dt>
            <dd className="break-all font-mono text-[13px] text-slate-300">{h.server}</dd>
          </div>
        )}
        {h.powered_by && (
          <div className="contents">
            <dt className="text-slate-500">Powered by</dt>
            <dd className="break-all font-mono text-[13px] text-slate-300">{h.powered_by}</dd>
          </div>
        )}
        <div className="contents">
          <dt className="text-slate-500">Security headers</dt>
          <dd>
            <ul className="grid gap-1 sm:grid-cols-2">
              {Object.entries(h.security_headers).map(([name, present]) => (
                <li key={name} className="flex items-center gap-1.5 text-slate-300">
                  {present ? (
                    <Check className="h-3.5 w-3.5 text-blue-400" aria-label="present" />
                  ) : (
                    <X className="h-3.5 w-3.5 text-slate-500" aria-label="missing" />
                  )}
                  {name}
                </li>
              ))}
            </ul>
          </dd>
        </div>
      </dl>
    </details>
  );
}

export default function ReconReport({ recon, finalUrl }: { recon: Recon; finalUrl: string }) {
  return (
    <Section title="Who's behind it">
      <div className="grid gap-3 md:grid-cols-3">
        <ServerCard recon={recon} />
        <DomainCard recon={recon} />
        <CertificateCard recon={recon} finalUrl={finalUrl} />
      </div>
      <div className="mt-3 space-y-2">
        <DnsDetails recon={recon} />
        <TechDetails recon={recon} />
      </div>
    </Section>
  );
}

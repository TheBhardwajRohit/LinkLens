// The short version of a report: what to do now, the key facts at a glance, and a warning you can
// send to family. Everything here is built from the scan result; nothing comes from the page itself.

import { Check, Copy, Globe, Link2, Lock, LockOpen, MessageCircle, Server, ShieldQuestion, Users } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { Scan, Verdict } from "../lib/api";
import { formatAge } from "../lib/format";
import { defang } from "../lib/url";

const ADVICE: Record<Verdict, string[]> = {
  safe: [
    "No strong warning signs were found. You can open it, but stay careful.",
    "Never type a password, OTP, or UPI PIN on a page you reached from a message. Open the app or type the site's address yourself instead.",
  ],
  suspicious: [
    "Don't enter passwords, OTPs, card details, or your UPI PIN on this page.",
    "If the message claims to be from your bank, a delivery company, or the government, contact them through their official app or phone number, not this link.",
    "Don't forward the link without a warning.",
  ],
  dangerous: [
    "Don't open this link, and don't enter anything on it.",
    "Already entered details? Change that password now. If you shared card, bank, or UPI details, call your bank to block them.",
    "Don't forward the link without a warning.",
  ],
};

const ADVICE_LOOK: Record<Verdict, string> = {
  safe: "border-emerald-400/20 bg-emerald-400/[0.04]",
  suspicious: "border-amber-400/25 bg-amber-400/[0.05]",
  dangerous: "border-rose-400/30 bg-rose-500/[0.06]",
};

/** Plain advice for the verdict, with where to report a scam in India. */
export function Advice({ verdict }: { verdict: Verdict }) {
  return (
    <div className={`rounded-2xl border p-5 ${ADVICE_LOOK[verdict]}`}>
      <h3 className="font-display text-lg font-medium text-cream">What should you do?</h3>
      <ul className="mt-2 space-y-2 text-sm text-slate-200">
        {ADVICE[verdict].map((line) => (
          <li key={line} className="flex gap-2">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
            {line}
          </li>
        ))}
      </ul>
      {verdict !== "safe" && (
        <p className="mt-3 border-t border-white/[0.08] pt-3 text-sm text-slate-300">
          Lost money or shared details? Report it at{" "}
          <a
            href="https://cybercrime.gov.in"
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-blue-300 underline-offset-4 hover:underline"
          >
            cybercrime.gov.in
          </a>{" "}
          or call <span className="font-semibold text-cream">1930</span>, India's cyber fraud helpline.
        </p>
      )}
    </div>
  );
}

function Fact({ icon: Icon, label, children }: { icon: typeof Globe; label: string; children: ReactNode }) {
  return (
    <li className="flex gap-3 py-2.5">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-blue-400" aria-hidden="true" />
      <div className="min-w-0">
        <p className="text-xs text-slate-400">{label}</p>
        <p className="text-sm text-slate-100">{children}</p>
      </div>
    </li>
  );
}

/** The few facts most people want, without opening the detailed sections. */
export function KeyFacts({ scan }: { scan: Scan }) {
  const { recon, visit, analysis, blacklists, family } = scan;
  const shared = (analysis.final_link ?? analysis.link)?.free_hosting ?? null;
  const reg = recon?.registration;
  const server = recon?.server;
  const cert = recon?.certificate;
  const finalUrl = visit.final_url ?? visit.requested_url;
  const redirects = Math.max(visit.hops.length - 1, 0);
  const checked = (blacklists?.sources ?? []).filter((s) => !["not_configured", "skipped"].includes(s.status)).length;
  const listed = blacklists?.listed_by.length ?? 0;

  let age: ReactNode = "Unknown";
  if (shared) age = `A site on a free hosting service (${shared})`;
  else if (reg?.age_days !== null && reg?.age_days !== undefined) {
    age = reg.age_days < 30 ? <span className="text-amber-300">Only {formatAge(reg.age_days)} old</span> : `${formatAge(reg.age_days)} old`;
  }

  let where: string | null = null;
  if (server?.country || server?.as_org) where = [server.country, server.as_org].filter(Boolean).join(", hosted by ");

  let certificate: ReactNode;
  if (!finalUrl.startsWith("https:")) certificate = <span className="text-amber-300">No HTTPS, the page isn't encrypted</span>;
  else if (!cert) certificate = "Not captured";
  else certificate = cert.trusted ? "Trusted by browsers" : <span className="text-amber-300">Not trusted by browsers</span>;

  let familyText: string | null = null;
  if (family?.status === "matched" && family.family) familyText = `Matches "${family.family.label}"`;
  else if (family?.status === "similar") familyText = `Looks like ${family.scam_matches} known scam ${family.scam_matches === 1 ? "page" : "pages"}`;

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] px-5 py-3">
      <h3 className="pt-1 font-display text-lg font-medium text-cream">At a glance</h3>
      <ul className="divide-y divide-white/[0.06]">
        <Fact icon={Globe} label="Domain">
          {age}
        </Fact>
        {where && (
          <Fact icon={Server} label="Server">
            {where}
          </Fact>
        )}
        <Fact icon={finalUrl.startsWith("https:") ? Lock : LockOpen} label="Certificate">
          {certificate}
        </Fact>
        <Fact icon={Link2} label="Redirects">
          {redirects === 0 ? "None, it opens directly" : `${redirects} ${redirects === 1 ? "jump" : "jumps"} before the final page`}
        </Fact>
        {checked > 0 && (
          <Fact icon={ShieldQuestion} label="Blacklists">
            {listed > 0 ? (
              <span className="text-rose-300">Listed by {listed} of {checked} checked</span>
            ) : (
              `Not on any of the ${checked} lists checked`
            )}
          </Fact>
        )}
        {familyText && (
          <Fact icon={Users} label="Scam family">
            {familyText}
          </Fact>
        )}
      </ul>
    </div>
  );
}

/** The link without its query string, defanged: safe to send, and no personal data from the link. */
function shareableLink(url: string): string {
  try {
    const u = new URL(url);
    return defang(`${u.protocol}//${u.host}${u.pathname}`);
  } catch {
    return defang(url);
  }
}

function isLocal(): boolean {
  return ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);
}

/** A short warning message to copy or send on WhatsApp. */
export function warningText(scan: Scan, reportLink: string | null): string {
  const a = scan.analysis;
  const head =
    a.verdict === "dangerous"
      ? `Warning: LinkLens says this link is likely dangerous (${a.score}/100).`
      : `Careful: LinkLens found warning signs in this link (${a.score}/100).`;
  const lines = [head, `Link: ${shareableLink(scan.url)}`];
  if (a.scam_type) lines.push(`It looks like: ${a.scam_type.label}${a.scam_type.brand ? ` (${a.scam_type.brand})` : ""}.`);
  const reasons = a.reasons.slice(0, 2).map((r) => `- ${r.text}`);
  if (reasons.length) lines.push("Why:", ...reasons);
  lines.push("Don't open it, and never share passwords, OTPs, or bank details from a link like this.");
  if (reportLink) lines.push(`Full report: ${reportLink}`);
  return lines.join("\n");
}

const BUTTON =
  "inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm ring-1 transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300";

/** "Warn your family": scam links mostly spread as forwards, so make the warning easy to forward too. */
export function WarnFamily({ scan, reportLink }: { scan: Scan; reportLink: string | null }) {
  const [copied, setCopied] = useState(false);
  if (scan.analysis.verdict === "safe") return null;
  const text = warningText(scan, reportLink && !isLocal() ? reportLink : null);
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5 print:hidden">
      <h3 className="font-display text-lg font-medium text-cream">Warn your family</h3>
      <p className="mt-1 text-sm text-slate-300">
        Scam links spread through forwards. Send a short warning instead. The link in it is broken on purpose, so
        nobody can open it by accident.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          className={`${BUTTON} bg-white/[0.06] text-slate-100 ring-white/10 hover:bg-white/10`}
          onClick={() => {
            navigator.clipboard
              ?.writeText(text)
              .then(() => {
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1800);
              })
              .catch(() => {});
          }}
        >
          {copied ? <Check className="h-4 w-4 text-emerald-300" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
          {copied ? "Warning copied" : "Copy warning"}
        </button>
        <a
          href={`https://wa.me/?text=${encodeURIComponent(text)}`}
          target="_blank"
          rel="noopener noreferrer"
          className={`${BUTTON} bg-blue-600 font-medium text-white ring-blue-400/40 hover:bg-blue-500`}
        >
          <MessageCircle className="h-4 w-4" aria-hidden="true" />
          Send on WhatsApp
        </a>
      </div>
    </div>
  );
}

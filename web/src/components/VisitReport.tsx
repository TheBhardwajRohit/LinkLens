// Shows what the sandbox saw. Everything here came from a possibly dangerous page, so:
// the page is shown only as a screenshot (an image), and every address is defanged plain text.

import { Check, CircleAlert, Copy, ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { Hop, HopKind, Visit } from "../lib/api";
import { defang } from "../lib/url";

const HOP_LABEL: Record<HopKind, string> = {
  start: "Start",
  server: "Server redirect",
  header: "Refresh header",
  meta: "Meta refresh",
  script: "Script redirect",
  form: "Form sent by the page",
  page: "Page redirect",
};

const OUTCOME: Record<string, { text: string; tone: "good" | "warn" | "bad" | "muted"; icon: typeof ShieldCheck }> = {
  ok: { text: "Page captured", tone: "good", icon: ShieldCheck },
  timeout: { text: "Partial result: the page was slow", tone: "warn", icon: ShieldAlert },
  blocked: { text: "Stopped: the link leads somewhere private", tone: "bad", icon: ShieldX },
  unreachable: { text: "The site didn't respond", tone: "muted", icon: ShieldAlert },
  download: { text: "The link starts a download", tone: "warn", icon: ShieldAlert },
  crashed: { text: "The page crashed the sandbox browser", tone: "bad", icon: ShieldX },
  error: { text: "The page could not be opened", tone: "muted", icon: ShieldAlert },
};

const TONE = {
  good: "border-emerald-400/25 bg-emerald-400/5 text-emerald-300",
  warn: "border-amber-400/25 bg-amber-400/5 text-amber-300",
  bad: "border-rose-400/30 bg-rose-500/5 text-rose-300",
  muted: "border-line bg-ink/40 text-slate-300",
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard
          ?.writeText(text)
          .then(() => {
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1500);
          })
          .catch(() => {});
      }}
      className="shrink-0 rounded-md p-1.5 text-slate-400 transition hover:bg-white/5 hover:text-white focus-visible:outline-2 focus-visible:outline-cyan-300"
      aria-label={copied ? "Copied" : "Copy the defanged address"}
      title="Copy (defanged)"
    >
      {copied ? <Check className="h-4 w-4 text-emerald-300" /> : <Copy className="h-4 w-4" />}
    </button>
  );
}

function Address({ url }: { url: string }) {
  const safe = defang(url);
  return (
    <span className="flex min-w-0 items-start gap-1">
      <span className="min-w-0 break-all font-mono text-sm text-slate-200">{safe}</span>
      <CopyButton text={safe} />
    </span>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</h3>
      {children}
    </section>
  );
}

function HopRow({ hop, index }: { hop: Hop; index: number }) {
  return (
    <li className="flex gap-3">
      <span
        className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
          hop.blocked ? "bg-rose-500/15 text-rose-300" : "bg-cyan-400/10 text-cyan-300"
        }`}
      >
        {index + 1}
      </span>
      <div className="min-w-0 flex-1 pb-3">
        <p className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
          <span>{HOP_LABEL[hop.kind] ?? hop.kind}</span>
          {hop.status !== null && <span className="rounded bg-white/5 px-1.5 py-0.5 font-mono">{hop.status}</span>}
          {hop.blocked && (
            <span className="rounded bg-rose-500/15 px-1.5 py-0.5 text-rose-300">Blocked: {hop.reason}</span>
          )}
        </p>
        <Address url={hop.url} />
      </div>
    </li>
  );
}

export default function VisitReport({ visit }: { visit: Visit }) {
  const outcome = OUTCOME[visit.stopped ?? "ok"] ?? OUTCOME.error;
  const Icon = outcome.icon;

  return (
    <div className="mt-2 space-y-6">
      <div className={`rounded-xl border p-4 ${TONE[outcome.tone]}`}>
        <p className="flex items-center gap-2 font-medium">
          <Icon className="h-5 w-5" aria-hidden="true" />
          {outcome.text}
        </p>
        {visit.notes.length > 0 && (
          <ul className="mt-2 space-y-1 text-sm text-slate-300">
            {visit.notes.map((note) => (
              <li key={note} className="flex gap-2">
                <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
                {note}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-xs text-slate-500">
          Visual check only. The risk score and scam type arrive in a later phase. Took{" "}
          {(visit.duration_ms / 1000).toFixed(1)} s.
        </p>
      </div>

      {visit.screenshot_jpeg_b64 && (
        <Section title="Safe preview">
          <figure>
            <img
              src={`data:image/jpeg;base64,${visit.screenshot_jpeg_b64}`}
              alt="Screenshot of the page, taken inside the sandbox"
              className="w-full rounded-xl border border-line"
            />
            <figcaption className="mt-2 text-xs text-slate-500">
              A picture taken inside the sandbox. It's only an image, so nothing on it can run or be clicked.
            </figcaption>
          </figure>
        </Section>
      )}

      {visit.final_url && (
        <Section title="Final address">
          <Address url={visit.final_url} />
          {visit.title && (
            <p className="mt-1 break-words text-sm text-slate-400">
              Page title: <span className="text-slate-300">{visit.title}</span>
            </p>
          )}
        </Section>
      )}

      {visit.hops.length > 0 && (
        <Section title={`Link trail (${visit.hops.length} ${visit.hops.length === 1 ? "step" : "steps"})`}>
          <ol>
            {visit.hops.map((hop, i) => (
              <HopRow key={`${i}-${hop.url}`} hop={hop} index={i} />
            ))}
          </ol>
          {visit.pending_refresh && (
            <p className="mt-1 text-sm text-slate-400">
              The page would redirect again later, to <span className="font-mono">{defang(visit.pending_refresh)}</span>
            </p>
          )}
        </Section>
      )}

      {visit.blocked.length > 0 && (
        <Section title="Blocked by the sandbox">
          <ul className="space-y-1 text-sm">
            {visit.blocked.map((b) => (
              <li key={`${b.host}:${b.port}`} className="flex flex-wrap gap-x-2">
                <span className="font-mono text-slate-200">{defang(`${b.host}:${b.port}`)}</span>
                <span className="text-rose-300">{b.reason}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {visit.contacted_domains.length > 0 && (
        <Section title="Contacted domains">
          <details className="text-sm">
            <summary className="cursor-pointer text-slate-300 hover:text-white">
              The page contacted {visit.contacted_domains.length}{" "}
              {visit.contacted_domains.length === 1 ? "domain" : "domains"}
            </summary>
            <ul className="mt-2 columns-1 gap-6 sm:columns-2">
              {visit.contacted_domains.map((d) => (
                <li key={d} className="break-all font-mono text-slate-400">
                  {d.replaceAll(".", "[.]")}
                </li>
              ))}
            </ul>
          </details>
        </Section>
      )}
    </div>
  );
}

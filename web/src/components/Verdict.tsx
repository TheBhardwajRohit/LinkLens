// The verdict: a colored badge, the score, one plain sentence, and the reasons behind it.
// Colors mean verdicts here and nowhere else: green safe, amber suspicious, red dangerous.

import { Check, Copy, Info, RotateCcw, ShieldAlert, ShieldCheck, ShieldX, Tag, type LucideIcon } from "lucide-react";
import { useState } from "react";

import type { Analysis, Reason, Verdict } from "../lib/api";
import { resultLink } from "../lib/useScan";
import { Section } from "./ReportParts";

const LOOK: Record<Verdict, { label: string; icon: LucideIcon; badge: string; ring: string; bar: string; text: string }> = {
  safe: {
    label: "Looks safe",
    icon: ShieldCheck,
    badge: "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30",
    ring: "border-emerald-400/25 shadow-[0_30px_80px_-40px_rgba(16,185,129,0.6)]",
    bar: "bg-emerald-400",
    text: "text-emerald-300",
  },
  suspicious: {
    label: "Suspicious",
    icon: ShieldAlert,
    badge: "bg-amber-500/15 text-amber-300 ring-amber-400/30",
    ring: "border-amber-400/30 shadow-[0_30px_80px_-40px_rgba(245,158,11,0.6)]",
    bar: "bg-amber-400",
    text: "text-amber-300",
  },
  dangerous: {
    label: "Likely dangerous",
    icon: ShieldX,
    badge: "bg-rose-500/15 text-rose-300 ring-rose-400/30",
    ring: "border-rose-400/35 shadow-[0_30px_80px_-40px_rgba(244,63,94,0.7)]",
    bar: "bg-rose-500",
    text: "text-rose-300",
  },
};

export function VerdictCard({ analysis }: { analysis: Analysis }) {
  const look = LOOK[analysis.verdict];
  const Icon = look.icon;
  return (
    <div className={`rounded-2xl border bg-ink/50 p-5 sm:p-6 ${look.ring}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold ring-1 ${look.badge}`}>
            <Icon className="h-4 w-4" aria-hidden="true" />
            {look.label}
          </span>
          <p className="mt-3 max-w-xl font-display text-xl font-medium leading-snug text-cream sm:text-2xl">{analysis.summary}</p>
          {analysis.scam_type && (
            <p className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-white/5 px-2.5 py-1 text-sm text-slate-200 ring-1 ring-white/10">
              <Tag className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
              {analysis.scam_type.label}
              {analysis.scam_type.brand && <span className="text-slate-400"> · {analysis.scam_type.brand}</span>}
            </p>
          )}
        </div>
        <div className="text-right">
          <p className={`font-display text-5xl font-semibold leading-none ${look.text}`}>
            {analysis.score}
            <span className="text-lg font-medium text-slate-500">/100</span>
          </p>
          <p className="mt-1 text-xs text-slate-500">risk score</p>
        </div>
      </div>
      <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-white/5" role="img" aria-label={`Risk score ${analysis.score} out of 100`}>
        <div className={`h-full rounded-full ${look.bar}`} style={{ width: `${Math.max(analysis.score, 2)}%` }} />
      </div>
      <div className="mt-1.5 flex justify-between text-[11px] text-slate-600">
        <span>0 safe</span>
        <span>31 suspicious</span>
        <span>70 dangerous</span>
        <span>100</span>
      </div>
      {analysis.partial && (
        <p className="mt-4 flex items-start gap-2 text-sm text-slate-400">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          The page itself couldn't be checked, so this is based on the link, the domain, and the server only.
        </p>
      )}
    </div>
  );
}

function ReasonRow({ reason }: { reason: Reason }) {
  const risk = reason.points > 0;
  const strength = risk ? (reason.points >= 25 ? "bg-rose-500/15 text-rose-300" : reason.points >= 10 ? "bg-amber-500/15 text-amber-300" : "bg-white/5 text-slate-300") : "bg-emerald-500/10 text-emerald-300";
  return (
    <li className="flex items-start gap-3 py-2">
      <span className={`mt-0.5 w-12 shrink-0 rounded-md px-1.5 py-0.5 text-center font-mono text-xs font-semibold ${strength}`}>
        {risk ? `+${reason.points}` : reason.points}
      </span>
      <span className="text-sm text-slate-200">{reason.text}</span>
    </li>
  );
}

export function WhyFlagged({ analysis }: { analysis: Analysis }) {
  return (
    <Section title="Why we flagged it">
      {analysis.reasons.length === 0 ? (
        <p className="text-sm text-slate-400">No warning signs were found.</p>
      ) : (
        <ul className="divide-y divide-white/[0.06]">
          {analysis.reasons.map((r) => (
            <ReasonRow key={r.text} reason={r} />
          ))}
        </ul>
      )}
      {analysis.good_signs.length > 0 && (
        <>
          <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Good signs</p>
          <ul className="divide-y divide-white/[0.06]">
            {analysis.good_signs.map((r) => (
              <ReasonRow key={r.text} reason={r} />
            ))}
          </ul>
        </>
      )}
      <p className="mt-4 text-xs text-slate-500">
        Each warning sign adds points and each good sign takes some away. The total is capped between 0 and 100.
        These are simple rules for now, so treat the result as likely, not certain.
        {analysis.tranco_list && ` Popularity from Tranco list ${analysis.tranco_list}.`}
      </p>
    </Section>
  );
}

const LATER = [
  ["Family Finder", "which scam kit or group this belongs to"],
  ["Sibling Hunter", "other sites run by the same people"],
  ["Blacklist checks", "what Google Safe Browsing and others say"],
  ["Network Map", "a clickable map of every connection"],
  ["Download Report", "the whole report as a PDF"],
];

export function ComingSoon() {
  return (
    <Section title="Coming in later phases">
      <ul className="grid gap-2 sm:grid-cols-2">
        {LATER.map(([name, what]) => (
          <li key={name} className="rounded-lg border border-dashed border-white/10 px-3 py-2 text-sm">
            <span className="text-slate-300">{name}</span>
            <span className="text-slate-500">: {what}</span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

export function ResultActions({ id, saved, onScanAnother }: { id: string; saved: boolean; onScanAnother: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex flex-wrap gap-2">
      {saved && (
        <button
          type="button"
          onClick={() => {
            navigator.clipboard
              ?.writeText(resultLink(id))
              .then(() => {
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1800);
              })
              .catch(() => {});
          }}
          className="inline-flex items-center gap-2 rounded-lg bg-white/[0.06] px-3.5 py-2 text-sm text-slate-100 ring-1 ring-white/10 transition hover:bg-white/10"
        >
          {copied ? <Check className="h-4 w-4 text-emerald-300" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
          {copied ? "Link copied" : "Copy link to this result"}
        </button>
      )}
      <button
        type="button"
        onClick={onScanAnother}
        className="inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm text-slate-300 ring-1 ring-white/10 transition hover:text-white hover:ring-white/30"
      >
        <RotateCcw className="h-4 w-4" aria-hidden="true" />
        Scan another link
      </button>
    </div>
  );
}

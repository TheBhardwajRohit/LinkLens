// The verdict: a colored badge, the score, one plain sentence, and the reasons behind it.
// Colors mean verdicts here and nowhere else: green safe, amber suspicious, red dangerous.

import { Info, ListX, ShieldAlert, ShieldCheck, ShieldX, Tag, type LucideIcon } from "lucide-react";

import type { Analysis, Reason, Verdict } from "../lib/api";
import { Section } from "./ReportParts";

const LOOK: Record<
  Verdict,
  { label: string; icon: LucideIcon; badge: string; ring: string; bar: string; text: string; stroke: string }
> = {
  safe: {
    label: "Looks safe",
    icon: ShieldCheck,
    badge: "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30",
    ring: "border-emerald-400/25 shadow-[0_30px_80px_-40px_rgba(16,185,129,0.6)]",
    bar: "bg-emerald-400",
    text: "text-emerald-300",
    stroke: "stroke-emerald-400",
  },
  suspicious: {
    label: "Suspicious",
    icon: ShieldAlert,
    badge: "bg-amber-500/15 text-amber-300 ring-amber-400/30",
    ring: "border-amber-400/30 shadow-[0_30px_80px_-40px_rgba(245,158,11,0.6)]",
    bar: "bg-amber-400",
    text: "text-amber-300",
    stroke: "stroke-amber-400",
  },
  dangerous: {
    label: "Likely dangerous",
    icon: ShieldX,
    badge: "bg-rose-500/15 text-rose-300 ring-rose-400/30",
    ring: "border-rose-400/35 shadow-[0_30px_80px_-40px_rgba(244,63,94,0.7)]",
    bar: "bg-rose-500",
    text: "text-rose-300",
    stroke: "stroke-rose-500",
  },
};

/** A half-circle gauge: the arc fills with the verdict's colour up to the score. */
function ScoreDial({ score, verdict }: { score: number; verdict: Verdict }) {
  const look = LOOK[verdict];
  const filled = Math.min(Math.max(score, 0), 100);
  return (
    <div className="relative w-44 shrink-0" role="img" aria-label={`Risk score ${score} out of 100`}>
      <svg viewBox="0 0 120 68" className="w-full" aria-hidden="true">
        <path d="M 10 60 A 50 50 0 0 1 110 60" pathLength={100} fill="none" strokeWidth="10" strokeLinecap="round" className="stroke-white/10" />
        {filled > 0 && (
          <path
            d="M 10 60 A 50 50 0 0 1 110 60"
            pathLength={100}
            fill="none"
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={`${filled} 100`}
            className={look.stroke}
          />
        )}
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center">
        <p className={`font-display text-4xl font-semibold leading-none ${look.text}`}>{score}</p>
        <p className="mt-1 text-xs text-slate-400">risk score out of 100</p>
      </div>
    </div>
  );
}

export function VerdictCard({ analysis }: { analysis: Analysis }) {
  const look = LOOK[analysis.verdict];
  const Icon = look.icon;
  const top = analysis.reasons.slice(0, 3);
  const more = analysis.reasons.length - top.length;
  return (
    <div className={`rounded-2xl border bg-ink/50 p-5 sm:p-6 ${look.ring}`}>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
        <div className="min-w-0 flex-1 basis-60">
          <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold ring-1 ${look.badge}`}>
            <Icon className="h-4 w-4" aria-hidden="true" />
            {look.label}
          </span>
          <p className="mt-3 font-display text-xl font-medium leading-snug text-cream sm:text-2xl">{analysis.summary}</p>
          {analysis.scam_type && (
            <p className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-white/5 px-2.5 py-1 text-sm text-slate-200 ring-1 ring-white/10">
              <Tag className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
              {analysis.scam_type.label}
              {analysis.scam_type.brand && <span className="text-slate-400"> · {analysis.scam_type.brand}</span>}
            </p>
          )}
          {(analysis.listed_by ?? []).length > 0 && (
            <p className="mt-2 flex items-center gap-1.5 text-sm text-rose-200">
              <ListX className="h-4 w-4 shrink-0" aria-hidden="true" />
              Listed by {(analysis.listed_by ?? []).join(", ")}
            </p>
          )}
        </div>
        <ScoreDial score={analysis.score} verdict={analysis.verdict} />
      </div>
      <p className="mt-3 flex justify-between gap-2 text-xs text-slate-400">
        <span>0 to 30 safe</span>
        <span>31 to 69 suspicious</span>
        <span>70 to 100 likely dangerous</span>
      </p>
      {top.length > 0 && (
        <div className="mt-5 border-t border-white/[0.08] pt-4">
          <p className="text-sm font-semibold text-slate-200">Main reasons</p>
          <ul className="mt-1 divide-y divide-white/[0.06]">
            {top.map((r) => (
              <ReasonRow key={r.text} reason={r} />
            ))}
          </ul>
          {more > 0 && (
            <p className="mt-1 text-xs text-slate-400">
              {more} more {more === 1 ? "sign" : "signs"} under "Why we flagged it".
            </p>
          )}
        </div>
      )}
      {analysis.partial && (
        <p className="mt-4 flex items-start gap-2 text-sm text-slate-300">
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
          <p className="mt-4 text-sm font-semibold tracking-wide text-slate-200">Good signs</p>
          <ul className="divide-y divide-white/[0.06]">
            {analysis.good_signs.map((r) => (
              <ReasonRow key={r.text} reason={r} />
            ))}
          </ul>
        </>
      )}
      <p className="mt-4 text-xs text-slate-400">
        Each warning sign adds points and each good sign takes some away. The total is capped between 0 and 100.
        {analysis.model
          ? " The points come from fixed rules plus a model trained on known scam pages. Both can be wrong, so treat the result as likely, not certain."
          : " These are fixed rules, so treat the result as likely, not certain."}
        {analysis.tranco_list && ` Popularity from Tranco list ${analysis.tranco_list}.`}
      </p>
    </Section>
  );
}

// "Compared with other tools": after a scan, the visitor can ask VirusTotal and PhishTank about the
// same link and read their answers beside LinkLens's. Nothing is asked until they click, because
// both services have small free limits and VirusTotal adds what it's sent to a public dataset.
// OpenPhish is never asked: its terms forbid showing its data.

import { LoaderCircle, RefreshCw } from "lucide-react";
import { useState } from "react";

import { API_URL, compareScan, type Analysis, type Comparison, type Scan } from "../lib/api";
import { formatDate } from "../lib/format";
import { defang } from "../lib/url";
import { VERDICT_TEXT, VERDICT_WORD } from "../home/examples";
import { Section } from "./ReportParts";

export type CompareState =
  | { kind: "idle" }
  | { kind: "asking"; fresh: boolean }
  | { kind: "done"; comparison: Comparison }
  | { kind: "failed"; error: string };

/** The comparison for one report: what was saved with the scan, and a way to ask (again). */
export function useComparison(scan: Scan, example: boolean) {
  const [state, setState] = useState<CompareState>(scan.comparison ? { kind: "done", comparison: scan.comparison } : { kind: "idle" });
  const available = Boolean(API_URL) && !example && scan.saved;
  async function run(fresh: boolean) {
    if (!available) return;
    setState({ kind: "asking", fresh });
    const got = await compareScan(scan.id, fresh);
    setState(got.ok ? { kind: "done", comparison: got.comparison } : { kind: "failed", error: got.error });
  }
  return { state, run, available };
}

const BUTTON =
  "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-[15px] font-semibold transition-[background-color,transform] duration-150 active:scale-[0.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300 disabled:cursor-wait disabled:opacity-60";

/** The short way in, under the verdict. */
export function CompareButton({ onClick, state, available }: { onClick: () => void; state: CompareState; available: boolean }) {
  if (!available) return null;
  return (
    <div className="rounded-2xl bg-panel p-5 print:hidden">
      <p className="text-[17px] font-medium text-cream">How do other tools see this link?</p>
      <p className="mt-1 text-[15px] text-slate-300">Ask VirusTotal and PhishTank about the same link and compare.</p>
      <button type="button" onClick={onClick} disabled={state.kind === "asking"} className={`${BUTTON} mt-4 bg-blue-600 text-white hover:bg-blue-500`}>
        {state.kind === "asking" && <LoaderCircle className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />}
        {state.kind === "done" ? "See the comparison" : "Compare with other tools"}
      </button>
    </div>
  );
}

function ownScore(analysis: Analysis): number {
  const parts = [...analysis.reasons, ...analysis.good_signs].filter((r) => r.area !== "blacklist");
  return Math.max(0, Math.min(100, parts.reduce((sum, r) => sum + r.points, 0)));
}

function votes(n: number): string {
  return `${n} ${n === 1 ? "vote" : "votes"}`;
}

function minus(n: number): string {
  return n < 0 ? `−${Math.abs(n)}` : `${n}`;
}

const CARD = "rounded-xl bg-panel p-4 sm:p-5";

function Label({ children }: { children: string }) {
  return <p className="text-sm text-slate-400">{children}</p>;
}

function LinkLensCard({ analysis }: { analysis: Analysis }) {
  const own = ownScore(analysis);
  return (
    <div className={`${CARD} sm:col-span-2`}>
      <Label>LinkLens</Label>
      <p className={`mt-1 font-display text-2xl font-semibold ${VERDICT_TEXT[analysis.verdict]}`}>
        {VERDICT_WORD[analysis.verdict]}, {analysis.score}
      </p>
      <p className="mt-1 text-base text-slate-200">{analysis.summary}</p>
      <p className="mt-2 text-sm text-slate-400">
        {own === analysis.score
          ? "All of it from LinkLens's own checks of the page and the link."
          : `${own} of it from LinkLens's own checks; the rest from other services' lists.`}{" "}
        {analysis.reasons.length} reasons in the report.
      </p>
    </div>
  );
}

function VirusTotalCard({ answer }: { answer: Comparison["virustotal"] }) {
  const r = answer.report;
  return (
    <div className={CARD}>
      <Label>VirusTotal</Label>
      {r ? (
        <>
          <p className="mt-1 font-display text-4xl font-semibold leading-none tabular-nums text-cream">
            {r.stats.malicious} / {r.engines}
          </p>
          <p className="mt-2 text-base text-slate-200">security vendors flag it as malicious</p>
          {r.stats.suspicious > 0 && <p className="text-sm text-slate-400">{r.stats.suspicious} more call it suspicious.</p>}
          {r.flagged.length > 0 && (
            <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Vendors that flag it">
              {r.flagged.slice(0, 8).map((f) => (
                <li key={f.engine} className="rounded-lg bg-white/[0.06] px-2.5 py-1 text-sm text-slate-200">
                  {f.engine}
                  {f.label && <span className="text-slate-400">: {f.label}</span>}
                </li>
              ))}
              {r.flagged.length > 8 && <li className="px-1 py-1 text-sm text-slate-400">and {r.flagged.length - 8} more</li>}
            </ul>
          )}
          {r.reputation !== null && r.reputation !== 0 && (
            <p className="mt-3 text-sm text-slate-400">
              Community score <span className="font-medium tabular-nums text-slate-200">{minus(r.reputation)}</span> ({votes(r.votes.malicious ?? 0)} malicious, {r.votes.harmless ?? 0} harmless)
            </p>
          )}
          <p className="mt-2 text-sm text-slate-400">
            {answer.fresh ? "Fresh analysis just now." : r.last_analysis ? `Its last analysis: ${formatDate(r.last_analysis)}.` : ""}
            {r.first_seen && ` First seen ${formatDate(r.first_seen)}.`} No reasons are given beyond the vendor labels.
          </p>
        </>
      ) : (
        <p className="mt-1 text-base text-slate-200">{answer.note}</p>
      )}
    </div>
  );
}

function PhishTankCard({ answer }: { answer: Comparison["phishtank"] }) {
  const line =
    answer.status === "listed"
      ? answer.verified
        ? `Confirmed phish, report #${answer.phish_id}`
        : `Reported, as #${answer.phish_id}`
      : answer.status === "not_listed"
        ? "No record of this link"
        : "No answer";
  return (
    <div className={CARD}>
      <Label>PhishTank</Label>
      <p className="mt-1 text-[17px] font-medium text-slate-100">{line}</p>
      <p className="text-sm text-slate-400">{answer.note}</p>
      <p className="mt-2 text-sm text-slate-400">A list of links its members reported. It doesn't look at the page.</p>
    </div>
  );
}

function OpenPhishCard() {
  return (
    <div className={CARD}>
      <Label>OpenPhish</Label>
      <p className="mt-1 text-[17px] font-medium text-slate-100">Not asked</p>
      <p className="text-sm text-slate-400">
        A list of links you download, refreshed every 12 hours for free users. Its terms forbid showing its data to
        anyone, so LinkLens never shows it.
      </p>
    </div>
  );
}

export default function CompareReport({
  analysis,
  state,
  run,
  available,
}: {
  analysis: Analysis;
  state: CompareState;
  run: (fresh: boolean) => void;
  available: boolean;
}) {
  const asking = state.kind === "asking";
  return (
    <Section title="Compared with other tools">
      {!available && state.kind !== "done" && (
        <p className="rounded-xl bg-panel px-4 py-3 text-base text-slate-200">
          Comparing needs the scanner to be online and a saved scan. Try it on a link you scan yourself.
        </p>
      )}
      {available && state.kind === "idle" && (
        <div className="rounded-xl bg-panel p-5">
          <p className="text-base text-slate-200">
            LinkLens can ask VirusTotal and PhishTank about this same link, so you can see their answers beside its own.
            Only the cleaned link is sent, without personal details.
          </p>
          <button type="button" onClick={() => run(false)} className={`${BUTTON} mt-4 bg-blue-600 text-white hover:bg-blue-500`}>
            Compare now
          </button>
        </div>
      )}
      {asking && (
        <p className="flex items-center gap-3 rounded-xl bg-panel px-4 py-4 text-base text-slate-200" role="status">
          <LoaderCircle className="h-5 w-5 shrink-0 animate-spin text-blue-300 motion-reduce:animate-none" aria-hidden="true" />
          {state.fresh
            ? "VirusTotal is running a fresh analysis. This takes up to a minute."
            : "Asking VirusTotal and PhishTank..."}
        </p>
      )}
      {state.kind === "failed" && (
        <div className="rounded-xl bg-panel p-5">
          <p className="text-base text-slate-200">{state.error}</p>
          <button type="button" onClick={() => run(false)} className={`${BUTTON} mt-3 bg-white/[0.07] text-slate-100 hover:bg-white/[0.12]`}>
            Try again
          </button>
        </div>
      )}
      {state.kind === "done" && (
        <div className="space-y-4">
          <div className="grid gap-2 sm:grid-cols-2">
            <LinkLensCard analysis={analysis} />
            <VirusTotalCard answer={state.comparison.virustotal} />
            <PhishTankCard answer={state.comparison.phishtank} />
            <div className="sm:col-span-2">
              <OpenPhishCard />
            </div>
          </div>
          <p className="text-sm text-slate-400">
            Asked {formatDate(state.comparison.asked_at)} about {defang(state.comparison.url)}.
          </p>
          {available && state.comparison.virustotal.status !== "skipped" && state.comparison.virustotal.status !== "not_configured" && (
            <div className="rounded-xl bg-panel p-5 print:hidden">
              <p className="text-base text-slate-200">
                VirusTotal's answer above is what it already knew. You can ask all its vendors to look again now. Its
                own guide says every link sent this way joins a dataset its community can see.
              </p>
              <button
                type="button"
                onClick={() => run(true)}
                disabled={asking}
                className={`${BUTTON} mt-3 bg-white/[0.07] text-slate-100 hover:bg-white/[0.12]`}
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                Ask VirusTotal for a fresh analysis
              </button>
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

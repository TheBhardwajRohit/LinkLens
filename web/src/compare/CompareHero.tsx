// The comparison page's first screen, built like the other two pages: two tones split down the
// middle. Left, the headline. Right, the answer board: pick one of the tested links and read what
// LinkLens, VirusTotal, PhishTank, and OpenPhish said about it, from the saved run.

import { ArrowDown, Link2 } from "lucide-react";
import { useState, type CSSProperties } from "react";

import { CopyButton } from "../components/ReportParts";
import { VERDICT_TEXT, VERDICT_WORD } from "../home/examples";
import { defang } from "../lib/url";
import { Dial, PILL, points } from "../site/parts";
import SiteHeader from "../site/SiteHeader";
import { communityScore, ledger, phishTankAnswer, runDate, TESTED, vtAnswer, vtReport, minus, type Tested } from "./data";

function Board({ link }: { link: Tested }) {
  const ll = link.linklens;
  const vt = vtAnswer(link);
  const flagged = vtReport(link).flagged ?? [];
  const community = communityScore(link);
  const pt = phishTankAnswer(link);
  const { lines, raised } = ledger(ll);

  return (
    <div key={link.url} className="band-in rounded-2xl bg-ink/60 p-2">
      <div className="flex items-center gap-2 px-3 pt-2.5">
        <Link2 className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
        <p className="min-w-0 flex-1 break-all text-[15px] text-slate-100">{defang(link.url)}</p>
        <CopyButton text={link.url} label="Copy this harmless link" />
      </div>
      <p className="px-3 pb-3 pt-1 text-sm text-slate-400">{link.what}</p>

      <div className="flex flex-col gap-4 rounded-xl bg-panel p-4 sm:flex-row sm:gap-5 sm:p-5">
        <Dial score={ll.score} verdict={ll.verdict} className="w-28 self-start" />
        <div className="min-w-0">
          <p className="text-sm text-slate-400">LinkLens</p>
          <p className={`font-display text-2xl font-semibold ${VERDICT_TEXT[ll.verdict]}`}>{VERDICT_WORD[ll.verdict]}</p>
          <ul className="mt-2 space-y-1">
            {lines.map((r) => (
              <li key={r.text} className={`flex gap-3 text-[15px] leading-snug ${r.quiet ? "text-slate-400" : "text-slate-200"}`}>
                <span className="w-9 shrink-0 text-right font-medium tabular-nums text-slate-400">{points(r.points)}</span>
                <span className="min-w-0">{r.text}</span>
              </li>
            ))}
          </ul>
          {raised && <p className="mt-2 text-sm text-slate-400">{raised}</p>}
        </div>
      </div>

      <div className="mt-2 grid gap-2 sm:grid-cols-5">
        <div className="rounded-xl bg-panel p-4 sm:col-span-3">
          <p className="text-sm text-slate-400">VirusTotal</p>
          {vt.count ? (
            <p className="mt-1 font-display text-4xl font-semibold leading-none tabular-nums text-cream">{vt.count}</p>
          ) : null}
          <p className={`${vt.count ? "mt-2 text-[15px]" : "mt-1 font-display text-xl font-semibold text-cream"} text-slate-200`}>{vt.line}</p>
          {flagged.length > 0 && (
            <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Vendors that flag it">
              {flagged.slice(0, 4).map((f) => (
                <li key={f.engine} className="rounded-lg bg-white/[0.06] px-2.5 py-1 text-sm text-slate-200">
                  {f.engine}
                </li>
              ))}
              {flagged.length > 4 && <li className="px-1 py-1 text-sm text-slate-400">and {flagged.length - 4} more</li>}
            </ul>
          )}
          {vt.note && <p className="mt-3 text-sm text-slate-400">{vt.note}</p>}
          {community !== null && community !== 0 && (
            <p className="mt-2 text-sm text-slate-400">
              Community score <span className="font-medium tabular-nums text-slate-200">{minus(community)}</span>
            </p>
          )}
        </div>
        <div className="grid gap-2 sm:col-span-2">
          <div className="rounded-xl bg-panel p-4">
            <p className="text-sm text-slate-400">PhishTank</p>
            <p className="mt-1 text-[15px] font-medium text-slate-100">{pt.line}</p>
            <p className="text-sm text-slate-400">{pt.note}</p>
          </div>
          <div className="rounded-xl bg-panel p-4">
            <p className="text-sm text-slate-400">OpenPhish</p>
            <p className="mt-1 text-[15px] font-medium text-slate-100">Not asked</p>
            <p className="text-sm text-slate-400">Its terms forbid showing its data.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CompareHero() {
  const [picked, setPicked] = useState(0);
  const link = TESTED[picked];

  return (
    <section className="relative grid min-h-[max(100svh,640px)] grid-cols-1 lg:grid-cols-2">
      <SiteHeader page="compare" />

      <div id="top" className="flex flex-col justify-end bg-ink px-5 pb-12 pt-28 sm:px-10 lg:pb-16">
        <h1 className="lines font-display text-[clamp(2.6rem,5.4vw,6rem)] font-semibold leading-[0.98] tracking-[-0.03em] text-cream">
          <span className="line">
            <span data-line style={{ "--i": 0 } as CSSProperties}>
              Same link.
            </span>
          </span>
          <span className="line">
            <span data-line style={{ "--i": 1 } as CSSProperties}>
              Four answers.
            </span>
          </span>
        </h1>
        <div className="after-lines">
          <p className="mt-6 max-w-[46ch] text-xl leading-relaxed text-slate-200">
            On {runDate()} we gave the same eight harmless links to VirusTotal, PhishTank and LinkLens. Pick one and
            compare what each said.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3">
            <a href="#every" className={`${PILL} bg-blue-600 text-white hover:bg-blue-500`}>
              See every result
              <ArrowDown className="h-4 w-4" aria-hidden="true" />
            </a>
            <a href="#method" className="text-[17px] text-slate-200 underline-offset-4 transition-colors hover:text-white hover:underline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-300">
              How we tested
            </a>
          </div>
        </div>
      </div>

      <div className="flex items-center bg-panel px-4 pb-10 pt-6 sm:px-8 lg:px-10 lg:pt-24">
        <div data-ui className="mx-auto w-full max-w-[640px]">
          <div role="radiogroup" aria-label="Tested link" className="flex flex-wrap gap-1.5">
            {TESTED.map((t, i) => (
              <button
                key={t.url}
                type="button"
                role="radio"
                aria-checked={i === picked}
                onClick={() => setPicked(i)}
                className={`rounded-full px-3.5 py-1.5 text-sm transition-[background-color,color,transform] duration-150 active:scale-[0.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300 ${
                  i === picked ? "bg-blue-600 font-medium text-white" : "bg-white/[0.07] text-slate-100 hover:bg-white/[0.12]"
                }`}
              >
                {t.name}
              </button>
            ))}
          </div>
          <div className="mt-4" aria-live="polite">
            <Board link={link} />
          </div>
        </div>
      </div>
    </section>
  );
}

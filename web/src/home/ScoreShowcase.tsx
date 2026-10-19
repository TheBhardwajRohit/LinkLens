// "Every point has a reason": the verdict switch, blown up. Picking a verdict turns the whole field
// that verdict's colour, changes the heading's last word, and lists the reasons behind that score.

import { useState } from "react";

import type { Verdict } from "../lib/api";
import { SHOWCASE, total } from "./examples";
import { Reveal, points } from "./parts";

const FIELD: Record<Verdict, string> = {
  safe: "bg-[#065f46]",
  suspicious: "bg-[#92400e]",
  dangerous: "bg-[#9f1239]",
};

const WORD: Record<Verdict, string> = { safe: "safe", suspicious: "suspicious", dangerous: "dangerous" };
const OPTIONS: { id: Verdict; label: string }[] = [
  { id: "safe", label: "Safe" },
  { id: "suspicious", label: "Suspicious" },
  { id: "dangerous", label: "Dangerous" },
];

export default function ScoreShowcase() {
  const [verdict, setVerdict] = useState<Verdict>("dangerous");
  const example = SHOWCASE[verdict];
  const score = total(example.reasons);

  return (
    <section
      aria-labelledby="score-heading"
      // The field keeps its own white text in both themes.
      className={`showcase relative overflow-hidden px-5 py-20 transition-colors duration-500 sm:px-10 lg:min-h-[92svh] lg:py-24 ${FIELD[verdict]}`}
    >
      <div className="relative z-10 max-w-xl">
        <Reveal>
          <h2 id="score-heading" className="font-display text-[clamp(1.75rem,2.6vw,2.5rem)] font-semibold tracking-[-0.02em] text-white">
            This one looks {WORD[verdict]}.
          </h2>
        </Reveal>
        <Reveal order={1}>
          <p className="mt-3 max-w-[46ch] text-[17px] leading-relaxed text-white/90">
            Every sign a scan finds adds points or takes them away, and the report lists each one. Pick a verdict to see
            the reasons behind an example score.
          </p>
        </Reveal>
        <Reveal order={2}>
          <p className="mt-8 break-all text-[15px] text-white/85">{example.link}</p>
          <ul className="mt-3 max-w-md space-y-2 text-[17px]" aria-live="polite">
            {example.reasons.map((r) => (
              <li key={r.text} className="flex items-start justify-between gap-4 text-white">
                <span>{r.text}</span>
                <span className="shrink-0 font-semibold tabular-nums">{points(r.points)}</span>
              </li>
            ))}
            <li className="flex justify-between gap-4 pt-2 font-semibold text-white">
              <span>Score</span>
              <span className="tabular-nums">{score}</span>
            </li>
          </ul>
        </Reveal>
      </div>

      {/* The control itself, at poster size. Every size inside is in em, so one font-size scales it. */}
      <div className="mt-14 lg:absolute lg:bottom-16 lg:right-10 lg:mt-0">
        <div data-ui className="showcase-control w-[22em] rounded-[1.4em] bg-black/25 p-[0.5em] text-white">
          <div role="radiogroup" aria-label="Verdict" className="grid grid-cols-3 gap-[0.25em]">
            {OPTIONS.map((o) => (
              <button
                key={o.id}
                type="button"
                role="radio"
                aria-checked={verdict === o.id}
                onClick={() => setVerdict(o.id)}
                className={`rounded-[1em] px-[0.4em] py-[0.7em] text-[0.8em] font-semibold transition-[background-color,color,transform] duration-200 active:scale-[0.97] focus-visible:outline-[0.12em] focus-visible:outline-white ${
                  verdict === o.id ? "bg-white text-slate-900" : "text-white/85 hover:bg-white/15"
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
          <div className="px-[0.7em] pb-[0.5em] pt-[0.9em]">
            <p className="flex items-baseline gap-[0.15em] font-display font-semibold leading-none">
              <span className="text-[3.6em] tabular-nums tracking-[-0.03em]">{score}</span>
              <span className="text-[1em] text-white/75">/ 100</span>
            </p>
            <div className="mt-[0.6em] h-[0.45em] overflow-hidden rounded-full bg-white/20" aria-hidden="true">
              <div className="h-full origin-left rounded-full bg-white transition-transform duration-500" style={{ transform: `scaleX(${score / 100})` }} />
            </div>
            <p className="mt-[0.5em] flex justify-between text-[0.5em] text-white/80">
              <span>0 to 30 safe</span>
              <span>31 to 69 suspicious</span>
              <span>70 to 100 dangerous</span>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

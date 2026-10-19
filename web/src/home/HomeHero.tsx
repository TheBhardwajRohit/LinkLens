// First screen: the headline and the one action on the left, and on the right a working example:
// a scam text message whose link LinkLens lifts out, defangs, and checks in front of you.

import { ArrowRight, Check, LoaderCircle, MessageSquareText } from "lucide-react";
import { useReducedMotion } from "motion/react";
import { useEffect, useRef, useState, type CSSProperties } from "react";

import { ThemeSwitch } from "../components/NavBar";
import { SCANNER } from "../lib/pages";
import { MESSAGES, STEPS, VERDICT_TEXT, VERDICT_WORD, type ExampleMessage } from "./examples";
import { Dial, PILL, points } from "./parts";

const REPO = "https://github.com/TheBhardwajRohit/LinkLens";
const STEP_MS = 420;

type Phase = { kind: "idle" } | { kind: "checking"; step: number } | { kind: "done" };

function MessageText({ message }: { message: ExampleMessage }) {
  const [before, after] = message.text.split("{link}");
  return (
    <p className="text-[15px] leading-relaxed text-slate-100">
      {before}
      {/* Defanged and never a link: nobody can open it from here. */}
      <span className="break-all rounded bg-blue-500/15 px-1 font-medium text-blue-200">{message.link}</span>
      {after}
    </p>
  );
}

function Result({ message }: { message: ExampleMessage }) {
  const top = message.reasons.slice(0, 3);
  return (
    <div className="hero-result">
      <div className="flex items-center gap-4">
        <Dial score={message.score} verdict={message.verdict} className="w-28" />
        <div className="min-w-0">
          <p className={`font-display text-xl font-semibold ${VERDICT_TEXT[message.verdict]}`}>{VERDICT_WORD[message.verdict]}</p>
          <p className="text-sm text-slate-300">{message.scamType}</p>
        </div>
      </div>
      <ul className="mt-4 space-y-2">
        {top.map((r) => (
          <li key={r.text} className="flex items-start justify-between gap-3 text-sm">
            <span className="text-slate-200">{r.text}</span>
            <span className="shrink-0 font-semibold tabular-nums text-slate-300">{points(r.points)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The live example. Picking a message resets it; "Check this link" plays the scan steps and lands
 * on that message's example verdict. The first message checks itself once, shortly after load. */
function MessageCheck() {
  const reduce = useReducedMotion() ?? false;
  const [index, setIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const timer = useRef<number | null>(null);
  const message = MESSAGES[index];

  function stop() {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
  }

  function run() {
    stop();
    if (reduce) {
      setPhase({ kind: "done" });
      return;
    }
    const tick = (step: number) => {
      if (step >= STEPS.length) {
        setPhase({ kind: "done" });
        return;
      }
      setPhase({ kind: "checking", step });
      timer.current = window.setTimeout(() => tick(step + 1), STEP_MS);
    };
    tick(0);
  }

  useEffect(() => {
    timer.current = window.setTimeout(run, reduce ? 0 : 1600);
    return stop;
    // Only once, on load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div data-ui className="w-full max-w-[460px] rounded-2xl bg-ink p-2 ring-1 ring-white/10">
      <div role="radiogroup" aria-label="Example message" className="grid grid-cols-3 gap-1 rounded-xl bg-white/[0.04] p-1">
        {MESSAGES.map((m, i) => (
          <button
            key={m.id}
            type="button"
            role="radio"
            aria-checked={i === index}
            onClick={() => {
              stop();
              setIndex(i);
              setPhase({ kind: "idle" });
            }}
            className={`rounded-lg px-2 py-2 text-sm transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-blue-300 ${
              i === index ? "bg-panel font-medium text-cream" : "text-slate-300 hover:bg-white/[0.06] hover:text-white"
            }`}
          >
            {m.tab}
          </button>
        ))}
      </div>

      <div className="px-3 pb-3 pt-4">
        <p className="flex items-center gap-2 text-sm text-slate-400">
          <MessageSquareText className="h-4 w-4" aria-hidden="true" />
          <span className="font-medium text-slate-200">{message.sender}</span> · Example message
        </p>
        <div className="mt-2 rounded-2xl rounded-tl-md bg-white/[0.06] px-4 py-3">
          <MessageText message={message} />
        </div>

        <div className="mt-4 min-h-[15.5rem]" aria-live="polite">
          {phase.kind === "idle" && (
            <button
              type="button"
              onClick={run}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-[15px] font-semibold text-white transition-[background-color,transform] duration-150 hover:bg-blue-500 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300"
            >
              Check this link
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
          {phase.kind === "checking" && (
            <ol className="space-y-2 px-1 text-sm">
              {STEPS.map((label, i) => (
                <li key={label} className="flex items-center gap-2.5">
                  <span className="flex h-4 w-4 items-center justify-center" aria-hidden="true">
                    {i < phase.step && <Check className="h-4 w-4 text-blue-400" />}
                    {i === phase.step && <LoaderCircle className="h-4 w-4 animate-spin text-blue-300" />}
                    {i > phase.step && <span className="h-1.5 w-1.5 rounded-full bg-slate-500" />}
                  </span>
                  <span className={i > phase.step ? "text-slate-400" : "text-slate-200"}>{label}</span>
                </li>
              ))}
            </ol>
          )}
          {phase.kind === "done" && (
            <>
              <Result message={message} />
              <p className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-slate-400">
                Example result, not a live scan.
                <button
                  type="button"
                  onClick={run}
                  className="font-medium text-blue-300 underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-blue-300"
                >
                  Check again
                </button>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function HomeHero() {
  return (
    <section className="relative grid min-h-[max(100svh,640px)] lg:grid-cols-2">
      <header className="absolute inset-x-0 top-0 z-10 flex items-center justify-between gap-4 px-5 py-5 sm:px-10">
        <a
          href="#top"
          className="font-display text-xl font-bold tracking-tight text-cream focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-300"
        >
          LinkLens
        </a>
        <nav aria-label="Main" className="flex items-center gap-5 text-[15px] text-slate-200">
          <a href="#how" className="hidden transition-colors hover:text-white sm:inline">
            How it works
          </a>
          <a href={REPO} target="_blank" rel="noopener noreferrer" className="hidden transition-colors hover:text-white sm:inline">
            GitHub
          </a>
          <a href={SCANNER} className="font-medium text-blue-300 transition-colors hover:text-blue-200">
            Scanner
          </a>
          <ThemeSwitch />
        </nav>
      </header>

      <div id="top" className="order-2 flex flex-col justify-end bg-ink px-5 pb-14 pt-10 sm:px-10 lg:order-1 lg:pb-16">
        <h1 className="lines font-display text-[clamp(2.6rem,5.4vw,6rem)] font-semibold leading-[0.98] tracking-[-0.03em] text-cream">
          <span className="line">
            <span data-line style={{ "--i": 0 } as CSSProperties}>
              Don't click it.
            </span>
          </span>
          <span className="line">
            <span data-line style={{ "--i": 1 } as CSSProperties}>
              Check it.
            </span>
          </span>
        </h1>
        <div className="after-lines">
          <p className="mt-6 max-w-[44ch] text-xl leading-relaxed text-slate-200">
            LinkLens opens a suspicious link in a sealed browser, so you see where it goes and who runs it without ever
            opening it yourself.
          </p>
          <a href={SCANNER} className={`${PILL} mt-8 bg-blue-600 text-white hover:bg-blue-500`}>
            Check a link
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </a>
        </div>
      </div>

      <div className="order-1 flex min-h-[58svh] items-center justify-center bg-panel px-4 pb-10 pt-24 lg:order-2 lg:min-h-0 lg:px-10 lg:py-24">
        <MessageCheck />
      </div>
    </section>
  );
}

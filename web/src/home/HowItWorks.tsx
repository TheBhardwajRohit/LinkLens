// "How a check works": three exchanges, each what you give and what comes back.

import { Ban, Check, CircleSlash, Link2, Lock, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";

import { MESSAGES, STEPS, VERDICT_TEXT, VERDICT_WORD } from "./examples";
import { Dial, Reveal, points } from "./parts";

const KYC = MESSAGES[0];

// One exchange per row: what you give on the left, what comes back on the right. Phones stack them.
function Exchange({ say, call, response }: { say: string; call: ReactNode; response: ReactNode }) {
  return (
    <div className="grid gap-6 lg:grid-cols-12 lg:gap-16">
      <div className="lg:col-span-5">
        <Reveal>
          <p className="font-display text-2xl font-medium text-cream">{say}</p>
        </Reveal>
        <Reveal order={1} className="mt-4">
          {call}
        </Reveal>
      </div>
      <Reveal order={2} className="lg:col-span-7 lg:pt-12">
        {response}
      </Reveal>
    </div>
  );
}

function PastedLink() {
  return (
    <div data-ui className="flex items-center gap-3 rounded-xl bg-panel px-4 py-3.5 ring-1 ring-white/10">
      <Link2 className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
      <p className="min-w-0 flex-1 truncate text-[15px] text-slate-100">hxxps://sbi-kyc-update[.]example/verify?mobile=98XXXXXX21</p>
      <span className="shrink-0 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white">Scan link</span>
    </div>
  );
}

function CleanedLink() {
  const rows = [
    { icon: Check, text: "Turned back into a normal link" },
    { icon: Check, text: "Your phone number removed from the link before anything else sees it" },
    { icon: Check, text: "Not a private or internal address, so it may be visited" },
  ];
  return (
    <div data-ui className="rounded-xl bg-white/[0.04] p-4 ring-1 ring-white/[0.08]">
      <p className="break-all text-sm text-slate-200">
        https://sbi-kyc-update.example/verify?mobile=<span className="rounded bg-white/10 px-1 text-slate-300">[removed]</span>
      </p>
      <ul className="mt-3 space-y-1.5 text-sm text-slate-300">
        {rows.map(({ icon: Icon, text }) => (
          <li key={text} className="flex items-start gap-2">
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-blue-400" aria-hidden="true" />
            {text}
          </li>
        ))}
      </ul>
    </div>
  );
}

function StepsDone() {
  return (
    <ol data-ui className="space-y-1.5 rounded-xl bg-panel px-4 py-3.5 text-[15px] ring-1 ring-white/10">
      {STEPS.slice(0, 4).map((s, i) => (
        <li key={s} className="flex items-center gap-2.5">
          <Check className={`h-4 w-4 ${i < 3 ? "text-blue-400" : "text-slate-500"}`} aria-hidden="true" />
          <span className={i < 3 ? "text-slate-200" : "text-slate-400"}>{s}</span>
        </li>
      ))}
    </ol>
  );
}

function Journey() {
  const hops = [
    { host: "sbi-kyc-update[.]example", note: "302, sent on" },
    { host: "track-redirect[.]example", note: "302, sent on" },
    { host: "secure-yono-login[.]example", note: "200, final page" },
  ];
  return (
    <div data-ui className="rounded-xl bg-white/[0.04] p-4 ring-1 ring-white/[0.08]">
      <p className="text-sm font-medium text-slate-200">Link journey</p>
      <ol className="mt-3 space-y-2">
        {hops.map((h, i) => (
          <li key={h.host} className="flex items-center gap-3 text-sm">
            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${i === hops.length - 1 ? "bg-blue-400" : "bg-slate-500"}`} aria-hidden="true" />
            <span className="min-w-0 flex-1 truncate text-slate-100">{h.host}</span>
            <span className="shrink-0 text-slate-400">{h.note}</span>
          </li>
        ))}
      </ol>
      <ul className="mt-4 space-y-1.5 rounded-lg bg-ink/50 p-3 text-sm">
        <li className="flex items-center gap-2 text-rose-300">
          <CircleSlash className="h-4 w-4 shrink-0" aria-hidden="true" />
          The page tried 10.0.0.8, a private address. Blocked.
        </li>
        <li className="flex items-center gap-2 text-slate-300">
          <Ban className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
          It offered yono-update.apk. Not downloaded.
        </li>
      </ul>
    </div>
  );
}

function Verdict() {
  return (
    <div data-ui className="rounded-2xl bg-panel p-5 ring-1 ring-rose-400/30 sm:p-6">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <Dial score={KYC.score} verdict={KYC.verdict} className="w-36" />
        <div className="min-w-0 flex-1 basis-56">
          <p className={`flex items-center gap-2 font-display text-2xl font-semibold ${VERDICT_TEXT[KYC.verdict]}`}>
            <ShieldAlert className="h-6 w-6" aria-hidden="true" />
            {VERDICT_WORD[KYC.verdict]}
          </p>
          <p className="mt-1 text-[15px] text-slate-200">This looks like a fake SBI page that asks for your OTP and UPI PIN.</p>
        </div>
      </div>
      <div className="mt-5 grid gap-x-8 gap-y-5 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div>
          <p className="text-sm font-semibold text-slate-200">Why we flagged it</p>
          <ul className="mt-2 text-sm">
            {KYC.reasons.map((r) => (
              <li key={r.text} className="flex items-start justify-between gap-3 py-1.5">
                <span className="text-slate-200">{r.text}</span>
                <span className={`shrink-0 font-semibold tabular-nums ${r.points < 0 ? "text-emerald-300" : "text-slate-300"}`}>
                  {points(r.points)}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 flex justify-between rounded-lg bg-white/[0.06] px-3 py-2 text-sm font-semibold text-cream">
            <span>Risk score</span>
            <span className="tabular-nums">{KYC.score} of 100</span>
          </p>
        </div>
        <div className="rounded-xl bg-rose-500/[0.07] p-4 text-sm text-slate-200">
          <p className="font-semibold text-cream">What should you do?</p>
          <p className="mt-2">Don't open this link, and don't enter anything on it.</p>
          <p className="mt-2">Already shared details? Call your bank to block them, then report it at cybercrime.gov.in or call 1930.</p>
          <p className="mt-3 flex items-center gap-2 text-slate-400">
            <Lock className="h-4 w-4" aria-hidden="true" />
            Example report
          </p>
        </div>
      </div>
    </div>
  );
}

export default function HowItWorks() {
  return (
    <section id="how" className="scroll-mt-6 px-5 py-28 sm:px-10 lg:py-44">
      <div className="mx-auto max-w-7xl">
        <Reveal>
          <h2 className="font-display text-[clamp(1.75rem,2.6vw,2.5rem)] font-semibold tracking-[-0.02em] text-cream">
            How a check works
          </h2>
        </Reveal>
        <div className="mt-14 space-y-24 lg:space-y-32">
          <Exchange say="First, paste the link you were sent." call={<PastedLink />} response={<CleanedLink />} />
          <Exchange say="Then LinkLens opens it, so you don't." call={<StepsDone />} response={<Journey />} />
          <Exchange
            say="You get a verdict, with every reason."
            call={<p className="text-[17px] text-slate-300">In about a minute, a plain report: the score, the scam it looks like, and each sign that led there.</p>}
            response={<Verdict />}
          />
        </div>
      </div>
    </section>
  );
}

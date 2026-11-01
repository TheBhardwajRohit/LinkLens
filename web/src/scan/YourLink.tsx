// "What happens to your link": the four things a scan does with a pasted link, in order. The
// heading stays pinned on the left while the steps pass on the right, each with a piece of the
// scanner's own interface. Every claim here is what the code does (redact.py, blacklists, the
// sandbox, storage); the link and the values shown are examples.

import { Ban, Check, CircleSlash, Copy, Link2, Lock } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Reveal } from "../site/parts";

function Step({ index, title, text, children }: { index: number; title: string; text: string; children: ReactNode }) {
  return (
    <li data-step={index} className="grid min-w-0 grid-cols-1 gap-6">
      <div>
        <Reveal>
          <h3 className="font-display text-2xl font-semibold leading-tight text-cream">{title}</h3>
        </Reveal>
        <Reveal order={1}>
          <p className="mt-3 max-w-[54ch] text-[17px] leading-relaxed text-slate-200">{text}</p>
        </Reveal>
      </div>
      <Reveal order={2}>{children}</Reveal>
    </li>
  );
}

/** A link before and after its personal details are removed (the comparison page shows it too). */
export function Cleaned() {
  return (
    <div data-ui className="rounded-2xl bg-panel p-2 ring-1 ring-white/10">
      <div className="flex items-center gap-3 rounded-xl px-3 py-3">
        <Link2 className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
        <p className="min-w-0 break-all text-[15px] text-slate-300">
          hxxps://kyc-update[.]example/verify?<span className="rounded bg-rose-500/15 px-1 text-rose-200">mobile=98XXXXXX21</span>&amp;
          <span className="rounded bg-rose-500/15 px-1 text-rose-200">token=Zx81kQ0pLm2vR7tYw4bN9cDs</span>
        </p>
      </div>
      <div className="flex items-center gap-3 rounded-xl bg-ink/60 px-3 py-3">
        <Check className="h-4 w-4 shrink-0 text-blue-400" aria-hidden="true" />
        <p className="min-w-0 break-all text-[15px] text-slate-100">
          https://kyc-update.example/verify?mobile=<span className="rounded bg-white/10 px-1">REDACTED</span>&amp;token=
          <span className="rounded bg-white/10 px-1">REDACTED</span>
        </p>
      </div>
    </div>
  );
}

const ASKED = [
  { source: "Google Safe Browsing", gets: "the cleaned link", answer: "Not listed" },
  { source: "Phishing lists", gets: "nothing, checked on LinkLens's own copy", answer: "Not listed" },
  { source: "urlscan.io", gets: "the site name only", answer: "2 earlier scans" },
  { source: "VirusTotal, URLhaus", gets: "the cleaned link, once keys are set", answer: "Not set up" },
  { source: "LinkLens's own scans", gets: "nothing, it's our database", answer: "First time seen" },
];

function Asked() {
  return (
    <div data-ui className="rounded-2xl bg-panel p-2 ring-1 ring-white/10">
      <ul>
        {ASKED.map((a, i) => (
          <li key={a.source} className={`grid gap-x-4 gap-y-0.5 rounded-xl px-3 py-3 sm:grid-cols-[minmax(0,1fr)_auto] ${i % 2 ? "" : "bg-ink/60"}`}>
            <div className="min-w-0">
              <p className="text-[15px] font-medium text-slate-100">{a.source}</p>
              <p className="text-sm text-slate-400">Gets {a.gets}</p>
            </div>
            <p className="self-center text-sm text-slate-200">{a.answer}</p>
          </li>
        ))}
      </ul>
      <p className="px-3 pb-2 pt-3 text-sm text-slate-400">Example answers. Each source has 7 seconds; a slow one never holds up the rest.</p>
    </div>
  );
}

const LOG = [
  { at: "0.0 s", icon: Check, text: "Loaded kyc-update[.]example", tone: "text-slate-100" },
  { at: "0.6 s", icon: Check, text: "Sent on to secure-login[.]example (302)", tone: "text-slate-100" },
  { at: "1.1 s", icon: CircleSlash, text: "The page asked for 10.0.0.8, a private address. Blocked.", tone: "text-rose-300" },
  { at: "2.3 s", icon: Ban, text: "It offered yono-update.apk. Not downloaded.", tone: "text-slate-100" },
  { at: "2.9 s", icon: Check, text: "Screenshot taken, browser closed", tone: "text-slate-100" },
];

function SandboxLog() {
  return (
    <div data-ui className="rounded-2xl bg-panel p-2 ring-1 ring-white/10">
      <p className="flex items-center gap-2 px-3 pb-2 pt-3 text-sm font-medium text-slate-200">
        <Lock className="h-4 w-4 text-blue-400" aria-hidden="true" />
        Sandbox visit, example
      </p>
      <ol className="rounded-xl bg-ink/60 py-1">
        {LOG.map(({ at, icon: Icon, text, tone }) => (
          <li key={at} className="flex items-start gap-3 px-3 py-2.5 text-[15px]">
            <span className="w-12 shrink-0 tabular-nums text-slate-400">{at}</span>
            <Icon className={`mt-1 h-4 w-4 shrink-0 ${tone}`} aria-hidden="true" />
            <span className={tone}>{text}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Saved() {
  return (
    <div data-ui className="rounded-2xl bg-panel p-5 ring-1 ring-white/10">
      <p className="text-[15px] font-medium text-slate-100">Report saved</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <p className="min-w-0 flex-1 truncate rounded-xl bg-ink/60 px-3 py-2.5 text-[15px] text-slate-200">
          thebhardwajrohit.github.io/LinkLens/scan/?scan=8f3c2a91
        </p>
        <span className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white">
          <Copy className="h-4 w-4" aria-hidden="true" />
          Copy link
        </span>
      </div>
      <ul className="mt-4 space-y-1.5 text-sm text-slate-300">
        <li className="flex gap-2">
          <Check className="mt-0.5 h-4 w-4 shrink-0 text-blue-400" aria-hidden="true" />
          Personal details in the link stay removed in the saved copy
        </li>
        <li className="flex gap-2">
          <Check className="mt-0.5 h-4 w-4 shrink-0 text-blue-400" aria-hidden="true" />
          The full screenshot is deleted after 90 days
        </li>
        <li className="flex gap-2">
          <Check className="mt-0.5 h-4 w-4 shrink-0 text-blue-400" aria-hidden="true" />
          The page's fingerprints stay, to spot the next copy of it
        </li>
      </ul>
    </div>
  );
}

const STEPS: { title: string; short: string; text: string; body: () => ReactNode }[] = [
  {
    title: "First, it's cleaned.",
    short: "Cleaned",
    text: "Phone numbers, emails, login tokens and session IDs are cut out of the link before anything else sees it.",
    body: () => <Cleaned />,
  },
  {
    title: "Then a few lists are asked.",
    short: "Lists asked",
    text: "Known scam lists answer in seconds, so you get a quick first answer. Private addresses are never sent anywhere.",
    body: () => <Asked />,
  },
  {
    title: "Only the sandbox opens it.",
    short: "Opened in the sandbox",
    text: "A sealed browser on LinkLens's server loads the page. It never types, clicks, submits or downloads, and it stops at a CAPTCHA.",
    body: () => <SandboxLog />,
  },
  {
    title: "Last, the report is kept.",
    short: "Report kept",
    text: "So you can reopen it or send it to someone. It's saved without the personal details that were in the link.",
    body: () => <Saved />,
  },
];

export default function YourLink() {
  const [active, setActive] = useState(0);
  const list = useRef<HTMLOListElement>(null);

  // The pinned column follows along: the step in the middle of the screen is the one marked.
  useEffect(() => {
    const items = list.current?.querySelectorAll<HTMLElement>("[data-step]");
    if (!items || !("IntersectionObserver" in window)) return;
    const watch = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setActive(Number(e.target.getAttribute("data-step")));
      },
      { rootMargin: "-45% 0px -45% 0px" },
    );
    items.forEach((el) => watch.observe(el));
    return () => watch.disconnect();
  }, []);

  return (
    <section id="your-link" className="scroll-mt-6 px-5 py-28 sm:px-10 lg:py-44">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-14 lg:grid-cols-12 lg:gap-16">
        <div className="lg:col-span-5">
          <div className="lg:sticky lg:top-28">
            <Reveal>
              <h2 className="font-display text-[clamp(1.75rem,2.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.02em] text-cream">
                What happens to your link
              </h2>
            </Reveal>
            <Reveal order={1}>
              <p className="mt-4 max-w-[40ch] text-[17px] leading-relaxed text-slate-200">
                Every scan does the same four things, in this order, and none of them happens on your device. You can
                watch each one tick off above while it runs.
              </p>
            </Reveal>
            <ol className="mt-10 hidden space-y-1 lg:block" aria-hidden="true">
              {STEPS.map((step, i) => (
                <li
                  key={step.short}
                  className={`flex items-center gap-3 rounded-xl px-4 py-3 text-[17px] transition-[background-color,color] duration-300 ${
                    i === active ? "bg-panel font-medium text-cream" : "text-slate-400"
                  }`}
                >
                  <span className={`h-2 w-2 rounded-full transition-colors duration-300 ${i <= active ? "bg-blue-400" : "bg-slate-600"}`} />
                  {step.short}
                </li>
              ))}
            </ol>
          </div>
        </div>
        <ol ref={list} className="space-y-20 lg:col-span-7 lg:space-y-24">
          {STEPS.map((step, i) => (
            <Step key={step.short} index={i} title={step.title} text={step.text}>
              {step.body()}
            </Step>
          ))}
        </ol>
      </div>
    </section>
  );
}

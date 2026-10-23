// Three more things a scan does, each a short statement beside a piece of the report that shows it.

import { Check, Copy, Lock, MessageCircle, Users } from "lucide-react";
import { useState, type ReactNode } from "react";

import { MESSAGES, VERDICT_WORD } from "./examples";
import { Reveal } from "./parts";

const KYC = MESSAGES[0];

// Every row has the same shape: the statement on the left, the piece of the report on the right,
// filling its column, so the three rows line up on the same edges.
function Row({ title, text, children }: { title: string; text: string; children: ReactNode }) {
  return (
    <div className="mx-auto grid max-w-7xl items-center gap-10 lg:grid-cols-12 lg:gap-16">
      <div className="lg:col-span-5">
        <Reveal>
          <h3 className="font-display text-[clamp(1.75rem,2.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.02em] text-cream">{title}</h3>
        </Reveal>
        <Reveal order={1}>
          <p className="mt-4 max-w-[42ch] text-[17px] leading-relaxed text-slate-200">{text}</p>
        </Reveal>
      </div>
      <Reveal order={2} className="lg:col-span-7">
        {children}
      </Reveal>
    </div>
  );
}

const SIBLINGS = [
  { tab: "Same server", count: 6 },
  { tab: "Same owner", count: 3 },
  { tab: "Same design", count: 14 },
  { tab: "Lookalike names", count: 9 },
];

const DESIGN = [
  { host: "sbi-yono-kyc[.]example", match: "Same code, same logo", seen: "2 days ago" },
  { host: "yono-sbi-verify[.]example", match: "Same layout and words", seen: "5 days ago" },
  { host: "onlinesbi-rewards[.]example", match: "Same code, same icon", seen: "3 weeks ago" },
  { host: "sbi-pan-link[.]example", match: "Same layout and logo", seen: "1 month ago" },
];

function FamilyFragment() {
  const [tab, setTab] = useState(2);
  return (
    <div data-ui className="rounded-2xl bg-panel p-5 ring-1 ring-white/10 sm:p-6">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-500/15 text-blue-300">
          <Users className="h-5 w-5" aria-hidden="true" />
        </span>
        <div>
          <p className="font-display text-lg font-semibold text-cream">Matches the "SBI YONO" scam family</p>
          <p className="text-sm text-slate-300">23 known scam pages on 17 sites, first seen in March. Example.</p>
        </div>
      </div>
      <div role="tablist" aria-label="Sibling sites" className="mt-5 flex flex-wrap gap-1 rounded-xl bg-ink/60 p-1">
        {SIBLINGS.map((s, i) => (
          <button
            key={s.tab}
            type="button"
            role="tab"
            aria-selected={tab === i}
            onClick={() => setTab(i)}
            className={`rounded-lg px-3 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-blue-300 ${
              tab === i ? "bg-blue-600 font-medium text-white" : "text-slate-300 hover:bg-white/[0.06] hover:text-white"
            }`}
          >
            {s.tab} <span className={tab === i ? "text-white/80" : "text-slate-400"}>{s.count}</span>
          </button>
        ))}
      </div>
      {tab === 2 ? (
        <ul className="mt-2 text-sm">
          {DESIGN.map((d) => (
            <li key={d.host} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 rounded-lg px-2 py-2.5 transition-colors hover:bg-white/[0.04]">
              <span className="text-slate-100">{d.host}</span>
              <span className="text-slate-400">
                {d.match}, seen {d.seen}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="py-4 text-sm text-slate-300">
          {SIBLINGS[tab].count} sites in this example. A real report lists each one, defanged, with why it matched.
        </p>
      )}
    </div>
  );
}

const RULES = [
  { rule: "Types into forms", answer: "Never" },
  { rule: "Downloads files", answer: "Never" },
  { rule: "Visits private or internal addresses", answer: "Blocked" },
  { rule: "Each redirect", answer: "Checked before it loads" },
  { rule: "CAPTCHAs and bot checks", answer: "Stops and says so" },
];

function SandboxFragment() {
  return (
    <div data-ui className="rounded-2xl bg-panel p-2 ring-1 ring-white/10">
      <p className="flex items-center gap-2 px-3 pb-2 pt-3 text-sm font-medium text-slate-200">
        <Lock className="h-4 w-4 text-blue-400" aria-hidden="true" />
        Sandbox rules, fixed for every scan
      </p>
      <ul className="rounded-xl bg-ink/60">
        {RULES.map((r) => (
          <li key={r.rule} className="flex items-center justify-between gap-4 px-3 py-3 text-[15px]">
            <span className="text-slate-200">{r.rule}</span>
            <span className="shrink-0 font-medium text-blue-300">{r.answer}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const WARNING = [
  `Warning: LinkLens says this link is ${VERDICT_WORD[KYC.verdict].toLowerCase()} (${KYC.score}/100).`,
  `Link: ${KYC.link}`,
  "It looks like: Banking fraud (SBI).",
  "Don't open it, and never share passwords, OTPs, or bank details from a link like this.",
].join("\n");

function WarnFragment() {
  const [copied, setCopied] = useState(false);
  return (
    <div data-ui className="rounded-2xl bg-panel p-5 ring-1 ring-white/10">
      <div className="rounded-2xl rounded-tr-md bg-emerald-500/[0.12] px-4 py-3">
        <p className="whitespace-pre-line text-[15px] leading-relaxed text-slate-100">{WARNING}</p>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => {
            navigator.clipboard
              ?.writeText(WARNING)
              .then(() => {
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1800);
              })
              .catch(() => {});
          }}
          className="inline-flex items-center gap-2 rounded-lg bg-white/[0.06] px-3.5 py-2 text-sm text-slate-100 ring-1 ring-white/10 transition-[background-color,transform] duration-150 hover:bg-white/10 active:scale-[0.97] focus-visible:outline-2 focus-visible:outline-blue-300"
        >
          {copied ? <Check className="h-4 w-4 text-emerald-300" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
          {copied ? "Warning copied" : "Copy warning"}
        </button>
        <span className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3.5 py-2 text-sm font-medium text-white">
          <MessageCircle className="h-4 w-4" aria-hidden="true" />
          Send on WhatsApp
        </span>
      </div>
    </div>
  );
}

export default function Capabilities() {
  return (
    <section className="space-y-32 px-5 py-28 sm:px-10 lg:space-y-44 lg:py-44">
      <Row
        title="It finds the whole gang."
        text="Scam pages are copied by the dozen. LinkLens compares each page with over 55,000 it has fingerprinted, and names the family and the sister sites."
      >
        <FamilyFragment />
      </Row>
      <Row
        title="It never opens on your phone."
        text="The link loads in a sealed browser on the scanner, with rules no page can change. You only ever see a screenshot."
      >
        <SandboxFragment />
      </Row>
      <Row
        title="Then warn your family."
        text="Scam links spread through forwards. Send a short warning back, with the link broken on purpose so nobody opens it by accident."
      >
        <WarnFragment />
      </Row>
    </section>
  );
}

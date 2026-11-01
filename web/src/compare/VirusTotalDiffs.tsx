// LinkLens beside VirusTotal, the service closest to it. The heading stays pinned on the left with
// the list of differences; on the right, each difference is shown with the real answers both gave
// for one of the tested links. Numbers come from the saved run, never typed in.

import { Lock } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { VERDICT_TEXT, VERDICT_WORD } from "../home/examples";
import { formatAge, formatDate } from "../lib/format";
import { defang } from "../lib/url";
import { Cleaned } from "../scan/YourLink";
import { Dial, points, Reveal } from "../site/parts";
import { byName, minus, shotUrl, vtAnswer, vtReport, type Reason, type Tested } from "./data";

const APPLE = byName("Fake apple.com");
const EXAMPLE = byName("example.com");
const GOOGLE = byName("Google's phishing test");
const MADE_UP = byName("Made-up SBI link");
const EICAR = byName("Antivirus test file");

const PANEL = "rounded-2xl bg-panel p-2";
const HALF = "rounded-xl bg-ink/60 p-4";

function Label({ children }: { children: ReactNode }) {
  return <p className="text-sm text-slate-400">{children}</p>;
}

function Reasons({ reasons }: { reasons: Reason[] }) {
  return (
    <ul className="mt-2 space-y-1.5">
      {reasons.map((r) => (
        <li key={r.text} className="flex gap-3 text-[15px] leading-snug text-slate-200">
          <span className="w-9 shrink-0 text-right font-medium tabular-nums text-slate-400">{points(r.points)}</span>
          <span className="min-w-0">
            {r.text}
            {r.area === "blacklist" && <span className="text-slate-400"> (another service's answer)</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}

function byPoints(link: Tested): Reason[] {
  return [...link.linklens.reasons].sort((a, b) => b.points - a.points);
}

function VtCount({ link }: { link: Tested }) {
  const vt = vtAnswer(link);
  return vt.count ? (
    <>
      <p className="mt-1 font-display text-4xl font-semibold leading-none tabular-nums text-cream">{vt.count}</p>
      <p className="mt-2 text-[15px] text-slate-200">{vt.line}</p>
    </>
  ) : (
    <>
      <p className="mt-1 font-display text-xl font-semibold text-cream">{vt.line}</p>
      {vt.note && <p className="mt-1 text-[15px] text-slate-200">{vt.note}</p>}
    </>
  );
}

function Flags({ link, limit }: { link: Tested; limit?: number }) {
  const report = vtReport(link);
  const flagged = report.flagged ?? [];
  const shown = limit ? flagged.slice(0, limit) : flagged;
  const quiet = (report.engines ?? 0) - flagged.length;
  return (
    <ul className="mt-3 space-y-1">
      {shown.map((f) => (
        <li key={f.engine} className="flex justify-between gap-3 rounded-lg bg-white/[0.04] px-3 py-1.5 text-[15px]">
          <span className="text-slate-100">{f.engine}</span>
          <span className={f.category === "malicious" ? "text-slate-200" : "text-slate-400"}>{f.label ?? f.category}</span>
        </li>
      ))}
      {limit && flagged.length > limit && <li className="px-3 py-1 text-sm text-slate-400">and {flagged.length - limit} more</li>}
      <li className="px-3 py-1 text-sm text-slate-400">{quiet} others: no problem found or no opinion</li>
    </ul>
  );
}

function WhyFragment() {
  return (
    <div data-ui className={`${PANEL} grid gap-2 md:grid-cols-2`}>
      <div className={HALF}>
        <Label>VirusTotal</Label>
        <VtCount link={APPLE} />
        <Flags link={APPLE} />
      </div>
      <div className={HALF}>
        <Label>LinkLens</Label>
        <p className={`mt-1 font-display text-2xl font-semibold ${VERDICT_TEXT[APPLE.linklens.verdict]}`}>
          {VERDICT_WORD[APPLE.linklens.verdict]}, {APPLE.linklens.score}
        </p>
        <Reasons reasons={byPoints(APPLE)} />
      </div>
    </div>
  );
}

function PuzzleFragment() {
  const report = vtReport(EXAMPLE);
  const votes = report.votes ?? {};
  return (
    <div data-ui className={`${PANEL} grid gap-2 md:grid-cols-5`}>
      <div className={`${HALF} md:col-span-3`}>
        <Label>VirusTotal</Label>
        <VtCount link={EXAMPLE} />
        <div className="mt-4 rounded-lg bg-white/[0.04] px-3 py-2.5">
          <p className="text-[15px] text-slate-200">
            Community score <span className="font-display text-2xl font-semibold tabular-nums text-cream">{minus(report.reputation ?? 0)}</span>
          </p>
          <p className="text-sm text-slate-400">
            {votes.malicious ?? 0} users voted malicious, {votes.harmless ?? 0} voted harmless
          </p>
        </div>
      </div>
      <div className={`${HALF} md:col-span-2`}>
        <Label>LinkLens</Label>
        <div className="mt-1 flex items-center gap-3">
          <Dial score={EXAMPLE.linklens.score} verdict={EXAMPLE.linklens.verdict} className="w-20" />
          <p className={`font-display text-2xl font-semibold ${VERDICT_TEXT[EXAMPLE.linklens.verdict]}`}>{VERDICT_WORD[EXAMPLE.linklens.verdict]}</p>
        </div>
        <Reasons reasons={EXAMPLE.linklens.good_signs} />
      </div>
    </div>
  );
}

function PageFragment() {
  const shot = shotUrl(GOOGLE);
  const vt = vtAnswer(GOOGLE);
  const found = byPoints(GOOGLE).filter((r) => r.area !== "blacklist");
  return (
    <div data-ui className={PANEL}>
      <div className="overflow-hidden rounded-xl bg-ink/60">
        <div className="flex items-center gap-3 bg-white/[0.04] px-3 py-2" aria-hidden="true">
          <span className="flex gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
            <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
            <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
          </span>
          <span className="flex min-w-0 items-center gap-1.5 truncate text-sm text-slate-400">
            <Lock className="h-3.5 w-3.5 shrink-0" />
            {defang(GOOGLE.linklens.visit.final_url ?? GOOGLE.url)}
          </span>
        </div>
        {shot && (
          <img
            src={shot}
            alt="Screenshot LinkLens took of Google's phishing test page in its sandbox"
            className="block aspect-[16/10] w-full bg-white object-cover object-top"
            loading="lazy"
          />
        )}
      </div>
      <div className="grid gap-2 p-2 pt-3 md:grid-cols-5">
        <div className="md:col-span-3">
          <Label>What LinkLens found on the page and in the link</Label>
          <Reasons reasons={found} />
        </div>
        <div className="md:col-span-2">
          <Label>VirusTotal for the same page</Label>
          <p className="mt-2 text-[15px] text-slate-200">
            {vt.count} {vt.line}. {vt.note}
          </p>
        </div>
      </div>
    </div>
  );
}

function OwnerFragment() {
  const o = APPLE.linklens.owner;
  const rows = [
    ["Registered with", o.registrar],
    ["Registered on", o.created ? `${formatDate(o.created)}, ${formatAge(o.age_days)} ago` : null],
    ["Hosted by", [o.network, o.country].filter(Boolean).join(", ") || null],
    ["Where to report abuse", o.abuse_email],
    ["Other sites on the same server", APPLE.linklens.siblings.same_server ? `${APPLE.linklens.siblings.same_server}` : null],
  ].filter((r): r is [string, string] => Boolean(r[1]));
  return (
    <div data-ui className={PANEL}>
      <div className="px-3 pb-3 pt-3">
        <p className="text-[15px] font-medium text-slate-100">Who's behind the fake apple.com</p>
        <p className="mt-1 text-sm text-slate-400">
          Looks like <span className="text-slate-200">{APPLE.linklens.unicode_host}</span>, really{" "}
          <span className="text-slate-200">{defang(APPLE.url)}</span>
        </p>
      </div>
      <dl className="rounded-xl bg-ink/60 py-1">
        {rows.map(([k, v]) => (
          <div key={k} className="grid gap-x-4 gap-y-0.5 px-3 py-2.5 sm:grid-cols-[13rem_minmax(0,1fr)]">
            <dt className="text-sm text-slate-400">{k}</dt>
            <dd className="min-w-0 break-words text-[15px] text-slate-100">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function IndiaFragment() {
  const ll = MADE_UP.linklens;
  return (
    <div data-ui className={`${PANEL} grid gap-2 md:grid-cols-5`}>
      <div className={`${HALF} md:col-span-3`}>
        <Label>LinkLens</Label>
        <p className={`mt-1 font-display text-2xl font-semibold ${VERDICT_TEXT[ll.verdict]}`}>
          {VERDICT_WORD[ll.verdict]}, {ll.score}
        </p>
        <p className="mt-1 text-[15px] text-slate-200">{ll.summary}</p>
        <Reasons reasons={byPoints(MADE_UP)} />
      </div>
      <div className={`${HALF} md:col-span-2`}>
        <Label>VirusTotal</Label>
        <VtCount link={MADE_UP} />
        <p className="mt-4 text-sm text-slate-400">
          We made this name up. It ends in .example, a name kept aside so it can never be a real site.
        </p>
      </div>
    </div>
  );
}

function StrongerFragment() {
  const ll = EICAR.linklens;
  return (
    <div data-ui className={`${PANEL} grid gap-2 md:grid-cols-2`}>
      <div className={HALF}>
        <Label>VirusTotal</Label>
        <VtCount link={EICAR} />
        <Flags link={EICAR} limit={6} />
      </div>
      <div className={HALF}>
        <Label>LinkLens</Label>
        <div className="mt-2 space-y-2">
          <div className="rounded-lg bg-white/[0.04] px-3 py-2.5">
            <p className="text-sm text-slate-400">From its own checks</p>
            <p className="font-display text-3xl font-semibold tabular-nums text-cream">{ll.own_score}</p>
          </div>
          <div className="rounded-lg bg-white/[0.04] px-3 py-2.5">
            <p className="text-sm text-slate-400">With VirusTotal's answer added</p>
            <p className={`font-display text-3xl font-semibold tabular-nums ${VERDICT_TEXT[ll.verdict]}`}>
              {ll.score} <span className="text-xl">{VERDICT_WORD[ll.verdict]}</span>
            </p>
          </div>
        </div>
        <p className="mt-3 text-sm text-slate-400">The file opens as plain text, so the sandbox saw a page with one line on it.</p>
      </div>
    </div>
  );
}

const flaggedApple = vtReport(APPLE).flagged?.length ?? 0;
const exampleReport = vtReport(EXAMPLE);
const eicarMalicious = vtReport(EICAR).stats?.malicious ?? 0;
const eicarFirstYear = vtReport(EICAR).first_seen?.slice(0, 4);

const DIFFS: { short: string; title: string; text: string; body: () => ReactNode }[] = [
  {
    short: "It says why",
    title: "It tells you why.",
    text: `For the fake apple.com, VirusTotal lists ${flaggedApple} security companies that flag it, each with a one-word label. LinkLens names the trick: letters from another alphabet that spell "apple". VirusTotal's answer becomes one of its reasons.`,
    body: () => <WhyFragment />,
  },
  {
    short: "No puzzles",
    title: "No numbers to puzzle over.",
    text: `None of VirusTotal's ${exampleReport.engines} vendors find anything wrong with example.com, yet its users' votes give it a community score of ${minus(exampleReport.reputation ?? 0)}. Which one should you believe? LinkLens says it looks safe and shows why.`,
    body: () => <PuzzleFragment />,
  },
  {
    short: "Shows the page",
    title: "It shows you the page, safely.",
    text: "LinkLens opens the link in a sealed browser on its own server and keeps a screenshot, so you see the trap without stepping in. On Google's phishing test page it found a password box on a free hosting site.",
    body: () => <PageFragment />,
  },
  {
    short: "Names the owner",
    title: "It tells you who runs it.",
    text: "In the same report: who registered the name and when, which network hosts it, where to report abuse, and how many other sites share its server.",
    body: () => <OwnerFragment />,
  },
  {
    short: "Knows Indian scams",
    title: "It knows Indian scams.",
    text: "SBI, HDFC, ICICI, India Post, UPI, KYC, Aadhaar and PAN are built into its checks, and its advice points to the 1930 helpline. VirusTotal refused our made-up SBI link. LinkLens read the address and called it a likely fake SBI page.",
    body: () => <IndiaFragment />,
  },
  {
    short: "Keeps links private",
    title: "Your link stays private.",
    text: "VirusTotal's own guide says every link sent to its API joins a dataset its community can see. LinkLens removes emails, phone numbers and tokens from a link before it asks any service, and keeps its scans on its own server.",
    body: () => (
      <div>
        <Cleaned />
        <p className="mt-3 text-sm text-slate-400">Example link. Only the cleaned version ever leaves LinkLens.</p>
      </div>
    ),
  },
  {
    short: "Where VirusTotal wins",
    title: "Where VirusTotal is stronger.",
    text: `Files. LinkLens never downloads anything, so on the standard antivirus test file its own checks found almost nothing, while ${eicarMalicious} of VirusTotal's vendors call it malware. VirusTotal also has history going back to ${eicarFirstYear}. That's why LinkLens asks it too.`,
    body: () => <StrongerFragment />,
  },
];

export default function VirusTotalDiffs() {
  const [active, setActive] = useState(0);
  const list = useRef<HTMLOListElement>(null);

  // The pinned column follows along: the difference in the middle of the screen is the one marked.
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
    <section id="virustotal" aria-labelledby="vt-heading" className="scroll-mt-6 px-5 py-28 sm:px-10 lg:py-44">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-14 lg:grid-cols-12 lg:gap-16">
        <div className="lg:col-span-5">
          <div className="lg:sticky lg:top-28">
            <Reveal>
              <h2 id="vt-heading" className="font-display text-[clamp(1.75rem,2.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.02em] text-cream">
                VirusTotal counts. LinkLens explains.
              </h2>
            </Reveal>
            <Reveal order={1}>
              <p className="mt-4 max-w-[42ch] text-[17px] leading-relaxed text-slate-200">
                VirusTotal is the closest service to LinkLens: paste a link, get an answer. It asks about 90 security
                companies and adds up what they say. LinkLens opens the page in a sealed browser and judges it itself.
              </p>
            </Reveal>
            <ol className="mt-10 hidden space-y-1 lg:block" aria-hidden="true">
              {DIFFS.map((d, i) => (
                <li
                  key={d.short}
                  className={`flex items-center gap-3 rounded-xl px-4 py-2.5 text-[17px] transition-[background-color,color] duration-300 ${
                    i === active ? "bg-panel font-medium text-cream" : "text-slate-400"
                  }`}
                >
                  <span className={`h-2 w-2 rounded-full transition-colors duration-300 ${i <= active ? "bg-blue-400" : "bg-slate-600"}`} />
                  {d.short}
                </li>
              ))}
            </ol>
          </div>
        </div>
        <ol ref={list} className="space-y-20 lg:col-span-7">
          {DIFFS.map((d, i) => (
            <li key={d.short} data-step={i} className="grid min-w-0 grid-cols-1 gap-6">
              <div>
                <Reveal>
                  <h3 className="font-display text-2xl font-semibold leading-tight text-cream">{d.title}</h3>
                </Reveal>
                <Reveal order={1}>
                  <p className="mt-3 max-w-[56ch] text-[17px] leading-relaxed text-slate-200">{d.text}</p>
                </Reveal>
              </div>
              <Reveal order={2}>{d.body()}</Reveal>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

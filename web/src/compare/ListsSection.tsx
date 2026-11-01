// PhishTank and OpenPhish, shown in the form each service really takes: PhishTank answers a lookup
// from its list of reported links (real answers from the run); OpenPhish hands out a file of links
// (shown as an illustration with made-up links, because its terms forbid showing its data).

import { FileText, Search } from "lucide-react";

import { VERDICT_TEXT, VERDICT_WORD } from "../home/examples";
import { defang } from "../lib/url";
import { Reveal } from "../site/parts";
import { byName, phishTankAnswer, TESTED } from "./data";

const MADE_UP = byName("Made-up SBI link");

// Made-up links on reserved .example names, shown defanged, only to show what the feed looks like.
const FEED = [
  "hxxps://secure-login.bank-alerts[.]example/session/verify",
  "hxxps://parcel-redelivery-fee[.]example/pay",
  "hxxp://wallet-sync.connect-dapp[.]example/",
  "hxxps://kyc-update.netbank-help[.]example/login",
  "hxxps://account-review.mail-support[.]example/",
  "hxxp://tax-refund-claim.gov-portal[.]example/form",
];

const reported = TESTED.filter((t) => t.phishtank.status === "listed");
const verified = reported.filter((t) => t.phishtank.verified);
const exampleListed = reported.some((t) => t.name === "example.com");
const googleListed = byName("Google's phishing test").phishtank.status === "listed";

function PhishTankFragment() {
  return (
    <div data-ui className="rounded-2xl bg-panel p-2">
      <div className="flex items-center gap-3 rounded-xl bg-ink/60 px-3 py-3">
        <Search className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
        <p className="text-[15px] text-slate-300">Is it a phish? Each tested link, looked up in PhishTank</p>
      </div>
      <ul className="mt-1">
        {TESTED.map((t, i) => {
          const answer = phishTankAnswer(t);
          return (
            <li key={t.url} className={`grid gap-x-4 gap-y-0.5 rounded-xl px-3 py-2.5 sm:grid-cols-[minmax(0,1fr)_auto] ${i % 2 ? "bg-white/[0.03]" : ""}`}>
              <p className="min-w-0 text-[15px] text-slate-100">{t.name}</p>
              <p className="text-[15px] text-slate-200 sm:text-right">
                {answer.line}
                <span className="block text-sm text-slate-400">{answer.note}</span>
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function OpenPhishFragment() {
  return (
    <div data-ui className="rounded-2xl bg-panel p-2">
      <div className="flex items-center gap-3 rounded-xl bg-ink/60 px-3 py-3">
        <FileText className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
        <p className="text-[15px] text-slate-300">feed.txt, refreshed every 12 hours</p>
      </div>
      <ol className="space-y-0.5 px-3 py-3">
        {FEED.map((line) => (
          <li key={line} className="break-all text-[15px] leading-relaxed text-slate-200">
            {line}
          </li>
        ))}
        <li className="text-[15px] text-slate-400">and so on, one link per line</li>
      </ol>
      <p className="px-3 pb-2 text-sm text-slate-400">Illustration with made-up links. OpenPhish's own data isn't shown.</p>
    </div>
  );
}

export default function ListsSection() {
  return (
    <section id="lists" aria-labelledby="lists-heading" className="scroll-mt-6 bg-panel/40 px-5 py-28 sm:px-10 lg:py-40">
      <div className="mx-auto max-w-7xl">
        <div className="max-w-3xl">
          <Reveal>
            <h2 id="lists-heading" className="font-display text-[clamp(1.75rem,2.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.02em] text-cream">
              PhishTank and OpenPhish are lists.
            </h2>
          </Reveal>
          <Reveal order={1}>
            <p className="mt-4 max-w-[58ch] text-[17px] leading-relaxed text-slate-200">
              Neither one looks at the link you give it. Each keeps a list of links that were already caught. A link
              nobody has caught yet isn't on the list, so there's nothing to say about it.
            </p>
          </Reveal>
        </div>

        <div className="mt-16 grid grid-cols-1 gap-14 lg:grid-cols-12 lg:gap-10">
          <div className="min-w-0 lg:col-span-7">
            <Reveal>
              <h3 className="font-display text-2xl font-semibold leading-tight text-cream">PhishTank: people report, people vote.</h3>
            </Reveal>
            <Reveal order={1}>
              <p className="mt-3 max-w-[56ch] text-[17px] leading-relaxed text-slate-200">
                Run by Cisco Talos. Members send in links they suspect and vote on each one. New members can't join right
                now: its sign-up page says registration is temporarily disabled.
              </p>
            </Reveal>
            <Reveal order={2} className="mt-6">
              <PhishTankFragment />
            </Reveal>
            <Reveal order={3}>
              <p className="mt-4 max-w-[56ch] text-[17px] leading-relaxed text-slate-200">
                {reported.length} of our {TESTED.length} links are in PhishTank, and {verified.length === 0 ? "none was ever verified" : `${verified.length} verified`}.
                {exampleListed && " One of them is example.com, which is safe."}
                {!googleListed && " Google's phishing test page isn't there at all."}
              </p>
            </Reveal>
          </div>

          <div className="min-w-0 lg:col-span-5">
            <Reveal>
              <h3 className="font-display text-2xl font-semibold leading-tight text-cream">OpenPhish: a list you download.</h3>
            </Reveal>
            <Reveal order={1}>
              <p className="mt-3 max-w-[48ch] text-[17px] leading-relaxed text-slate-200">
                Made by an automated system that hunts for phishing pages. The free version is a file of links,
                refreshed every 12 hours, for non-commercial use only. Its terms forbid showing its data to anyone, so
                this page shows none of it.
              </p>
            </Reveal>
            <Reveal order={2} className="mt-6">
              <OpenPhishFragment />
            </Reveal>
          </div>
        </div>

        <Reveal className="mt-16">
          <div className="grid gap-6 rounded-2xl bg-panel p-6 sm:p-8 lg:grid-cols-12 lg:items-center lg:gap-10">
            <div className="lg:col-span-7">
              <h3 className="font-display text-2xl font-semibold leading-tight text-cream">LinkLens doesn't wait for a list.</h3>
              <p className="mt-3 max-w-[56ch] text-[17px] leading-relaxed text-slate-200">
                It judges a link the first time anyone sees it, and still asks lists like these as one more input. Our
                made-up SBI link is on no list anywhere. LinkLens read it and called it a likely fake SBI page.
              </p>
            </div>
            <div data-ui className="rounded-xl bg-ink/60 p-4 lg:col-span-5">
              <p className="break-all text-[15px] text-slate-300">{defang(MADE_UP.url)}</p>
              <p className={`mt-2 font-display text-2xl font-semibold ${VERDICT_TEXT[MADE_UP.linklens.verdict]}`}>
                {VERDICT_WORD[MADE_UP.linklens.verdict]}, {MADE_UP.linklens.score}
              </p>
              <p className="text-[15px] text-slate-200">{MADE_UP.linklens.scam_type?.label}, copying {MADE_UP.linklens.scam_type?.brand}</p>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

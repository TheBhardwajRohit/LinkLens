// How the comparison was run, and what it leaves out, so the results can be checked and repeated.

import { Reveal } from "../site/parts";
import { runDate, TESTED } from "./data";

const refused = TESTED.filter((t) => t.vt_after?.refused);
const refusedMessage = refused[0]?.vt_after?.refused;

const FACTS: { term: string; text: string }[] = [
  {
    term: "When",
    text: `${runDate()}, in one evening. VirusTotal and PhishTank were asked first, then LinkLens scanned each link.`,
  },
  {
    term: "VirusTotal",
    text:
      `Its free API. We asked what it already knew, then asked all its vendors for a fresh analysis.` +
      (refused.length
        ? ` It refused ${refused.length === 1 ? "one link" : `${refused.length} links`} ("${refusedMessage}"): ${refused.map((t) => t.name).join(" and ")}.`
        : ""),
  },
  { term: "PhishTank", text: "Its public check-a-link lookup, which needs no key. LinkLens itself never uses PhishTank." },
  { term: "OpenPhish", text: "Not asked. Its terms forbid showing its data to anyone." },
  {
    term: "LinkLens",
    text: "A LinkLens scan server with its Google Safe Browsing and VirusTotal keys set, so its verdict counts their answers too. \"From its own checks\" is the score without any other service's list.",
  },
  {
    term: "The links",
    text: "Only harmless ones: test pages, real sites, and names that can't exist, so anyone can repeat the test safely. Live scam links are only ever opened on isolated servers, and aren't part of this test.",
  },
  {
    term: "Results change",
    text: "Every service keeps updating. These are the answers from that evening, and the saved run is in LinkLens's source code.",
  },
];

export default function Method() {
  return (
    <section id="method" aria-labelledby="method-heading" className="scroll-mt-6 px-5 py-28 sm:px-10 lg:py-40">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-12 lg:grid-cols-12 lg:gap-16">
        <div className="lg:col-span-4">
          <Reveal>
            <h2 id="method-heading" className="font-display text-[clamp(1.75rem,2.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.02em] text-cream">
              How we tested
            </h2>
          </Reveal>
          <Reveal order={1}>
            <p className="mt-4 max-w-[36ch] text-[17px] leading-relaxed text-slate-200">
              One script asked every service about the same links, one after another, and saved what each said.
            </p>
          </Reveal>
        </div>
        <dl className="space-y-1 lg:col-span-8">
          {FACTS.map((f, i) => (
            <Reveal key={f.term} order={Math.min(i, 4)}>
              <div className={`grid gap-x-8 gap-y-1 rounded-xl px-5 py-4 sm:grid-cols-[9rem_minmax(0,1fr)] ${i % 2 ? "bg-panel/50" : "bg-panel"}`}>
                <dt className="text-[17px] font-medium text-cream">{f.term}</dt>
                <dd className="text-[17px] leading-relaxed text-slate-200">{f.text}</dd>
              </div>
            </Reveal>
          ))}
        </dl>
      </div>
    </section>
  );
}

// What LinkLens checks with: its own numbers, and the sources it asks. Names only, no logos.

import { Reveal } from "./parts";

const TILES: { name: string; note: string; phone?: boolean }[] = [
  { name: "55,000+ pages", note: "fingerprinted from scams, scam feeds, and research data", phone: true },
  { name: "531 families", note: "groups of scam pages built from the same kit", phone: true },
  { name: "97.5% precise", note: "the page-reading model, tested on 15,558 pages it never saw", phone: true },
  { name: "Safe Browsing", note: "Google's list of dangerous sites", phone: true },
  { name: "phishunt.io", note: "fresh phishing links, every 2 hours", phone: true },
  { name: "PhishStats", note: "newly reported scam links, every 2 hours", phone: true },
  { name: "MaxMind", note: "where a server is, and who runs its network" },
  { name: "PhreshPhish", note: "a research set of real scam and honest pages" },
  { name: "Tranco", note: "the most visited sites, so real ones aren't flagged" },
  { name: "crt.sh", note: "every certificate a site has had" },
];

export default function ProofBoard() {
  return (
    <section aria-labelledby="proof-heading" className="px-3 py-24 sm:px-5 lg:py-36">
      <ul className="grid grid-cols-2 gap-1.5 lg:grid-cols-4 lg:gap-2">
        <li className="col-span-2 flex min-h-[120px] flex-col rounded-2xl bg-blue-600 p-6 lg:aspect-[3/1] lg:min-h-0">
          <Reveal>
            <h2 id="proof-heading" className="font-display text-[clamp(1.75rem,2.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.02em] text-white">
              What it checks with
            </h2>
          </Reveal>
          <p className="mt-2 max-w-md text-[17px] text-white/90">Numbers from the live library, October 2026.</p>
        </li>
        {TILES.map((t, i) => (
          <li
            key={t.name}
            className={`flex flex-col gap-3 rounded-2xl bg-panel p-6 lg:aspect-[3/2] ${t.phone ? "" : "hidden lg:flex"}`}
          >
            <Reveal order={i % 4}>
              <p className="font-display text-[clamp(1.5rem,2.6vw,2.5rem)] font-bold leading-tight tracking-[-0.01em] text-cream">{t.name}</p>
            </Reveal>
            <p className="text-[17px] leading-snug text-slate-300">{t.note}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

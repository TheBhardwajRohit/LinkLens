// "What LinkLens knows": the page library and what the scanner has been seeing, as tabs on the left
// and bands of facts on the right. Live from the scanner, or from the dated snapshot when offline.

import { ArrowUp } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { Trends } from "../lib/api";
import { formatCount, formatDate } from "../lib/format";
import { PILL, Reveal } from "../site/parts";
import { sourceLine, type Library } from "./library";

type Day = Trends["days"][number];

/** Every day of the window, oldest first, with empty days filled in, so gaps show as gaps. */
export function fillDays(days: Day[], windowDays: number, today = new Date()): Day[] {
  const byDate = new Map(days.map((d) => [d.date.slice(0, 10), d]));
  const out: Day[] = [];
  for (let back = windowDays - 1; back >= 0; back--) {
    const t = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - back));
    const key = t.toISOString().slice(0, 10);
    out.push(byDate.get(key) ?? { date: key, safe: 0, suspicious: 0, dangerous: 0 });
  }
  return out;
}

const SOURCE_NAMES: Record<string, string> = {
  scan: "Scans on this scanner",
  feed: "Scam feeds",
  phreshphish: "PhreshPhish research dataset",
};

type Band = { lead: string; title: string; note?: string; side?: ReactNode };

function capital(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function Share({ part, whole }: { part: number; whole: number }) {
  return (
    <span className="block h-2 w-24 overflow-hidden rounded-full bg-white/10 sm:w-32" aria-hidden="true">
      <span className="block h-full origin-left rounded-full bg-blue-500" style={{ transform: `scaleX(${whole ? part / whole : 0})` }} />
    </span>
  );
}

function Verdicts({ day }: { day: Day }) {
  const total = day.safe + day.suspicious + day.dangerous;
  return (
    <span className="flex h-2 w-24 overflow-hidden rounded-full bg-white/10 sm:w-32" aria-hidden="true">
      <span className="bg-rose-500" style={{ width: `${(day.dangerous / total) * 100}%` }} />
      <span className="bg-amber-400" style={{ width: `${(day.suspicious / total) * 100}%` }} />
      <span className="bg-emerald-400" style={{ width: `${(day.safe / total) * 100}%` }} />
    </span>
  );
}

function tabsFor(library: Library): { id: string; label: string; note: string; bands: Band[]; empty: string }[] {
  const { stats, trends } = library;
  const listed = stats.phishing_lists ? stats.phishing_lists.links + stats.phishing_lists.domains : 0;
  const libraryBands: Band[] = [
    { lead: formatCount(stats.pages), title: "pages fingerprinted", note: "Scam and honest pages, kept as fingerprints only. No page is ever stored whole." },
    { lead: formatCount(stats.families), title: "scam families", note: `${formatCount(stats.pages_in_families)} pages built from the same few kits, grouped every night.` },
  ];
  if (listed) {
    const updated = formatDate(stats.phishing_lists?.updated);
    libraryBands.push({
      lead: formatCount(listed),
      title: "links and domains on phishing lists",
      note: `Checked on LinkLens's own copy, so your link isn't sent anywhere for it.${updated ? ` Last refreshed ${updated}.` : ""}`,
    });
  }
  libraryBands.push({ lead: formatCount(stats.scans), title: "scans run on this scanner", note: "Each one adds its page to the library, so the next match is better." });
  for (const [source, labels] of Object.entries(stats.by_source)) {
    const total = Object.values(labels).reduce((a, b) => a + b, 0);
    libraryBands.push({
      lead: formatCount(total),
      title: SOURCE_NAMES[source] ?? source,
      note: labels.phish ? `${formatCount(labels.phish)} of them known scam pages` : undefined,
      side: <Share part={total} whole={stats.pages} />,
    });
  }

  const biggest = Math.max(...trends.families.map((f) => f.size), 1);
  const familyBands: Band[] = trends.families.map((f) => ({
    lead: formatCount(f.size),
    title: capital(f.label),
    note: `${formatCount(f.size)} pages on ${formatCount(f.sites)} ${f.sites === 1 ? "site" : "sites"}${f.last_seen ? `, last seen ${formatDate(f.last_seen)}` : ""}`,
    side: <Share part={f.size} whole={biggest} />,
  }));

  const topType = Math.max(...trends.scam_types.map((t) => t.count), 1);
  const typeBands: Band[] = trends.scam_types.map((t) => ({
    lead: formatCount(t.count),
    title: t.label,
    note: `${t.count === 1 ? "scan" : "scans"} judged this kind of scam`,
    side: <Share part={t.count} whole={topType} />,
  }));

  const days = fillDays(trends.days, trends.window_days, library.asOf)
    .filter((d) => d.safe + d.suspicious + d.dangerous > 0)
    .reverse();
  const dayBands: Band[] = days.map((d) => {
    const total = d.safe + d.suspicious + d.dangerous;
    return {
      lead: formatDate(d.date) ?? d.date,
      title: `${formatCount(total)} ${total === 1 ? "scan" : "scans"}`,
      note: `${d.dangerous} likely dangerous, ${d.suspicious} suspicious, ${d.safe} safe`,
      side: <Verdicts day={d} />,
    };
  });
  const scans = days.reduce((sum, d) => sum + d.safe + d.suspicious + d.dangerous, 0);

  return [
    { id: "library", label: "The library", note: `${formatCount(stats.pages)} pages`, bands: libraryBands, empty: "" },
    { id: "families", label: "Biggest families", note: `${trends.families.length} shown`, bands: familyBands, empty: "No scam families have formed yet." },
    { id: "types", label: "Kinds of scam", note: `${trends.scam_types.length} found`, bands: typeBands, empty: "No scan has been given a scam type yet." },
    { id: "days", label: "Scans by day", note: `${formatCount(scans)} in ${trends.window_days} days`, bands: dayBands, empty: `No scans in the last ${trends.window_days} days.` },
  ];
}

export default function Knows({ library, onCheck }: { library: Library; onCheck: () => void }) {
  const tabs = tabsFor(library);
  const [active, setActive] = useState(tabs[0].id);
  const tab = tabs.find((t) => t.id === active) ?? tabs[0];

  return (
    <section id="knows" aria-labelledby="knows-heading" className="scroll-mt-6 px-5 py-28 sm:px-10 lg:py-44">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <Reveal>
              <h2 id="knows-heading" className="font-display text-[clamp(1.75rem,2.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.02em] text-cream">
                What LinkLens knows
              </h2>
            </Reveal>
            <Reveal order={1}>
              <p className="mt-3 text-[17px] text-slate-200">Every scan is compared with all of this. {sourceLine(library)}</p>
            </Reveal>
          </div>
          <button type="button" onClick={onCheck} className={`${PILL} bg-blue-600 text-white hover:bg-blue-500`}>
            Check a link
            <ArrowUp className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="mt-14 grid grid-cols-1 gap-4 lg:grid-cols-[180px_minmax(0,1fr)] lg:gap-10">
          <div role="tablist" aria-label="What LinkLens knows" className="grid grid-cols-2 gap-1.5 lg:flex lg:flex-col">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                id={`knows-tab-${t.id}`}
                aria-selected={t.id === tab.id}
                aria-controls="knows-panel"
                onClick={() => setActive(t.id)}
                className={`flex min-h-16 shrink-0 flex-col justify-center rounded-xl px-4 py-2.5 text-left transition-[background-color,color,transform] duration-150 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-blue-300 ${
                  t.id === tab.id ? "bg-cream text-ink" : "bg-panel text-slate-100 hover:bg-white/[0.08]"
                }`}
              >
                <span className="text-[17px] font-medium">{t.label}</span>
                <span className={`text-sm ${t.id === tab.id ? "text-ink/70" : "text-slate-400"}`}>{t.note}</span>
              </button>
            ))}
          </div>

          <ul id="knows-panel" role="tabpanel" aria-labelledby={`knows-tab-${tab.id}`} className="space-y-1" key={tab.id}>
            {tab.bands.length === 0 && <li className="rounded-xl bg-panel px-5 py-6 text-[17px] text-slate-200">{tab.empty}</li>}
            {tab.bands.map((b, i) => (
              <li
                key={`${b.title}-${i}`}
                className={`band-in grid items-center gap-x-6 gap-y-1 rounded-xl px-5 py-4 sm:grid-cols-[8.5rem_minmax(0,1fr)_auto] ${i % 2 ? "bg-panel/50" : "bg-panel"}`}
                style={{ animationDelay: `${Math.min(i, 8) * 45}ms` }}
              >
                <span className="font-display text-xl font-semibold tabular-nums text-cream">{b.lead}</span>
                <span className="min-w-0">
                  <span className="block text-[17px] font-medium text-slate-100">{b.title}</span>
                  {b.note && <span className="block text-sm text-slate-400">{b.note}</span>}
                </span>
                {b.side && <span className="sm:justify-self-end">{b.side}</span>}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

// "What LinkLens knows": how many pages are in its library, where they came from, and when data
// last arrived. Only shown when a scanner is online, since the numbers come from its database.

import { Database, Fingerprint, ListX, RefreshCw, type LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { getStats, type Stats } from "../lib/api";
import { formatDate } from "../lib/format";

const SOURCE_NAMES: Record<string, string> = {
  scan: "Scans on this site",
  feed: "Scam feeds",
  phreshphish: "PhreshPhish research dataset",
};
const JOB_NAMES: Record<string, string> = {
  feeds: "Feed ingestion",
  phreshphish: "Dataset load",
  cluster: "Family grouping",
};

function count(n: number): string {
  return n.toLocaleString("en-IN");
}

function Tile({ icon: Icon, value, label }: { icon: LucideIcon; value: string; label: string }) {
  return (
    <li className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
      <Icon className="h-5 w-5 text-blue-400" aria-hidden="true" />
      <p className="mt-3 font-display text-3xl font-semibold text-cream">{value}</p>
      <p className="mt-1 text-sm text-slate-400">{label}</p>
    </li>
  );
}

export default function DataHealth({ online }: { online: boolean | null }) {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    if (!online) return;
    const controller = new AbortController();
    getStats(controller.signal).then((s) => {
      if (!controller.signal.aborted) setStats(s);
    });
    return () => controller.abort();
  }, [online]);

  if (!online || !stats) return null;
  const lists = stats.phishing_lists;
  const listed = lists ? lists.links + lists.domains : 0;
  const sources = Object.entries(stats.by_source);

  return (
    <section id="data" className="mx-auto max-w-[88rem] scroll-mt-8 px-5 pb-24 sm:px-8">
      <div className="max-w-2xl">
        <h2 className="font-display text-3xl font-medium tracking-tight text-cream sm:text-4xl">What LinkLens knows</h2>
        <p className="mt-4 text-slate-400">
          Every scan is compared with pages LinkLens has seen before. The library starts small and grows with each
          scan and each feed run, so matches get better over time.
        </p>
      </div>
      <ul className="mt-10 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile icon={Database} value={count(stats.pages)} label="pages fingerprinted" />
        <Tile icon={Fingerprint} value={count(stats.families)} label="scam families found" />
        <Tile icon={ListX} value={count(listed)} label="links and domains on phishing lists" />
        <Tile icon={RefreshCw} value={count(stats.scans)} label="scans run here" />
      </ul>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Where the pages came from</h3>
          {sources.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">Nothing yet. The first scan adds the first page.</p>
          ) : (
            <ul className="mt-3 divide-y divide-white/[0.06] text-sm">
              {sources.map(([source, labels]) => {
                const total = Object.values(labels).reduce((a, b) => a + b, 0);
                return (
                  <li key={source} className="flex flex-wrap items-baseline justify-between gap-x-4 py-2">
                    <span className="text-slate-200">{SOURCE_NAMES[source] ?? source}</span>
                    <span className="text-slate-400">
                      {count(total)} {total === 1 ? "page" : "pages"}
                      {labels.phish ? `, ${count(labels.phish)} known scams` : ""}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Latest data runs</h3>
          {stats.last_runs.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">
              No data job has run against this database yet. Scheduled feed runs start once a shared database exists.
            </p>
          ) : (
            <ul className="mt-3 divide-y divide-white/[0.06] text-sm">
              {stats.last_runs.map((run) => (
                <li key={run.job} className="py-2">
                  <p className="flex flex-wrap items-baseline justify-between gap-x-4">
                    <span className="text-slate-200">{JOB_NAMES[run.job] ?? run.job}</span>
                    <span className={run.ok ? "text-slate-400" : "text-amber-300"}>
                      {run.ok ? "finished" : "had a problem"} on {formatDate(run.finished_at)}
                    </span>
                  </p>
                  {run.note && <p className="mt-0.5 text-slate-500">{run.note}</p>}
                </li>
              ))}
            </ul>
          )}
          {lists?.updated && (
            <p className="mt-3 text-xs text-slate-500">Phishing lists last refreshed on {formatDate(lists.updated)}.</p>
          )}
        </div>
      </div>
    </section>
  );
}

// "Trends": what LinkLens has been seeing lately. Scans per day by verdict, the kinds of scam,
// the brands copied most in the page library, and the biggest scam families.

import { useEffect, useState } from "react";

import { getTrends, type Trends as TrendsData } from "../lib/api";
import { formatDate } from "../lib/format";

const count = (n: number) => n.toLocaleString("en-IN");

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</h3>
      {children}
    </div>
  );
}

/** A plain horizontal bar list: label, bar, number. */
function Bars({ rows }: { rows: { label: string; value: number }[] }) {
  const top = Math.max(...rows.map((r) => r.value), 1);
  return (
    <ul className="mt-3 space-y-2 text-sm">
      {rows.map((r) => (
        <li key={r.label}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="truncate text-slate-200">{r.label}</span>
            <span className="shrink-0 text-slate-400">{count(r.value)}</span>
          </div>
          <div className="mt-1 h-1.5 rounded-full bg-white/5">
            <div className="h-full rounded-full bg-blue-500/70" style={{ width: `${Math.max((r.value / top) * 100, 2)}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

function Days({ days }: { days: TrendsData["days"] }) {
  const top = Math.max(...days.map((d) => d.safe + d.suspicious + d.dangerous), 1);
  const total = days.reduce((sum, d) => sum + d.safe + d.suspicious + d.dangerous, 0);
  const bad = days.reduce((sum, d) => sum + d.dangerous, 0);
  return (
    <>
      <p className="mt-3 text-sm text-slate-300">
        {count(total)} scans, {count(bad)} judged likely dangerous.
      </p>
      <div
        className="mt-3 flex h-28 items-end gap-1"
        role="img"
        aria-label={`Scans per day: ${days.map((d) => `${d.date} ${d.safe + d.suspicious + d.dangerous}`).join(", ")}`}
      >
        {days.map((d) => {
          const sum = d.safe + d.suspicious + d.dangerous;
          return (
            <div key={d.date} className="flex min-w-1.5 flex-1 flex-col justify-end overflow-hidden rounded-sm" style={{ height: `${Math.max((sum / top) * 100, 4)}%` }} title={`${formatDate(d.date)}: ${sum} scans`}>
              <div className="bg-rose-500" style={{ flexGrow: d.dangerous }} />
              <div className="bg-amber-400" style={{ flexGrow: d.suspicious }} />
              <div className="bg-emerald-400" style={{ flexGrow: d.safe }} />
            </div>
          );
        })}
      </div>
      <p className="mt-2 flex flex-wrap gap-x-4 text-xs text-slate-500">
        <span>{formatDate(days[0].date)} to {formatDate(days[days.length - 1].date)}</span>
        <span className="text-emerald-300">safe</span>
        <span className="text-amber-300">suspicious</span>
        <span className="text-rose-300">likely dangerous</span>
      </p>
    </>
  );
}

export default function Trends({ online }: { online: boolean | null }) {
  const [trends, setTrends] = useState<TrendsData | null>(null);

  useEffect(() => {
    if (!online) return;
    const controller = new AbortController();
    getTrends(controller.signal).then((t) => {
      if (!controller.signal.aborted) setTrends(t);
    });
    return () => controller.abort();
  }, [online]);

  if (!online || !trends) return null;
  const nothing = trends.days.length === 0 && trends.brands.length === 0 && trends.families.length === 0;
  if (nothing) return null;

  return (
    <section id="trends" className="mx-auto max-w-[88rem] scroll-mt-8 px-5 pb-24 sm:px-8 print:hidden">
      <div className="max-w-2xl">
        <h2 className="font-display text-3xl font-medium tracking-tight text-cream sm:text-4xl">Trends</h2>
        <p className="mt-4 text-slate-400">
          What this scanner has been seeing. Scan numbers cover the last {trends.window_days} days; brands and families
          come from the whole page library.
        </p>
      </div>
      <div className="mt-10 grid gap-4 lg:grid-cols-2">
        {trends.days.length > 0 && (
          <Panel title="Scans per day">
            <Days days={trends.days} />
          </Panel>
        )}
        {trends.scam_types.length > 0 && (
          <Panel title="Kinds of scam found in scans">
            <Bars rows={trends.scam_types.map((t) => ({ label: t.label, value: t.count }))} />
          </Panel>
        )}
        {trends.brands.length > 0 && (
          <Panel title="Brands scam pages copy most">
            <Bars rows={trends.brands.map((b) => ({ label: b.brand, value: b.pages }))} />
          </Panel>
        )}
        {trends.families.length > 0 && (
          <Panel title="Biggest scam families">
            <ul className="mt-3 divide-y divide-white/[0.06] text-sm">
              {trends.families.map((f) => (
                <li key={f.id} className="flex flex-wrap items-baseline justify-between gap-x-4 py-2">
                  <span className="text-slate-200">
                    #{f.id}: {f.label}
                  </span>
                  <span className="text-slate-400">
                    {count(f.size)} pages on {count(f.sites)} sites
                    {f.last_seen ? `, last seen ${formatDate(f.last_seen)}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </Panel>
        )}
      </div>
    </section>
  );
}

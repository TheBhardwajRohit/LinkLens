// Scan several links at once (up to 10). They run one after another on the server; this list
// shows each one's verdict as it finishes and lets you open its full report.

import { ListPlus, LoaderCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { getScanStatus, startBulk, type BulkEntry, type Verdict } from "../lib/api";
import { defang } from "../lib/url";

const MAX = 10;
const POLL_MS = 3000;
const GIVE_UP_MS = 12 * 60 * 1000;

const VERDICT: Record<Verdict, { label: string; tone: string }> = {
  safe: { label: "Looks safe", tone: "text-emerald-300" },
  suspicious: { label: "Suspicious", tone: "text-amber-300" },
  dangerous: { label: "Likely dangerous", tone: "text-rose-300" },
};

type Row = BulkEntry & { verdict?: Verdict; score?: number; gaveUp?: boolean };

export default function BulkScan({ online, onOpen }: { online: boolean | null; onOpen: (id: string) => void }) {
  const [text, setText] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const timer = useRef(0);

  // Ask for each unfinished scan every few seconds until all are done.
  useEffect(() => {
    const waiting = rows.filter((r) => r.id && !r.verdict && !r.gaveUp);
    if (waiting.length === 0) return;
    const started = Date.now();
    const poll = async () => {
      const found = await Promise.all(waiting.map((r) => getScanStatus(r.id!)));
      setRows((current) =>
        current.map((row) => {
          const i = waiting.findIndex((w) => w.id === row.id);
          if (i < 0) return row;
          const status = found[i];
          if (status.state === "done" && status.verdict) return { ...row, verdict: status.verdict, score: status.score };
          if (status.state === "failed") return { ...row, gaveUp: true };
          return Date.now() - started > GIVE_UP_MS ? { ...row, gaveUp: true } : row;
        }),
      );
    };
    timer.current = window.setTimeout(poll, POLL_MS);
    return () => window.clearTimeout(timer.current);
  }, [rows]);

  if (!online) return null;
  const links = text
    .split(/\s+/)
    .map((l) => l.trim())
    .filter(Boolean);

  return (
    <details className="mt-4 max-w-xl text-sm print:hidden">
      <summary className="inline-flex cursor-pointer items-center gap-1.5 text-slate-400 hover:text-white">
        <ListPlus className="h-4 w-4" aria-hidden="true" />
        Scan several links at once
      </summary>
      <form
        className="mt-3"
        onSubmit={async (e) => {
          e.preventDefault();
          if (links.length === 0 || busy) return;
          setBusy(true);
          setError("");
          const result = await startBulk(links.slice(0, MAX));
          setBusy(false);
          if (result.ok) setRows(result.scans);
          else setError(result.error);
        }}
      >
        <label className="block text-slate-300">
          One link per line, up to {MAX}
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            spellCheck={false}
            className="mt-1 block w-full rounded-xl border border-white/15 bg-white/[0.045] px-3 py-2 font-mono text-[13px] text-slate-100 placeholder:font-sans placeholder:text-slate-500 focus:border-blue-400/60 focus:outline-none"
            placeholder={"example.com\nhxxp://another[.]example/login"}
          />
        </label>
        <div className="mt-2 flex items-center gap-3">
          <button
            type="submit"
            disabled={busy || links.length === 0}
            className="rounded-lg bg-blue-600 px-3.5 py-2 font-medium text-white ring-1 ring-inset ring-white/15 transition hover:bg-blue-500 disabled:opacity-60"
          >
            {busy ? "Starting" : `Scan ${Math.min(links.length, MAX) || ""} ${links.length === 1 ? "link" : "links"}`}
          </button>
          {links.length > MAX && <span className="text-amber-300">Only the first {MAX} will be scanned.</span>}
          {error && <span className="text-rose-300">{error}</span>}
        </div>
      </form>
      {rows.length > 0 && (
        <ul className="mt-3 divide-y divide-white/[0.06] rounded-xl border border-white/[0.08] bg-ink/40 px-3" aria-live="polite">
          {rows.map((row, i) => (
            <li key={`${i}-${row.url}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
              {/* A refused entry is shown exactly as typed (it is plain text here, never a link). */}
              <span className="min-w-0 flex-1 break-all font-mono text-[13px] text-slate-200">
                {row.error && !row.id ? row.url : defang(row.url)}
              </span>
              {row.error && <span className="text-amber-300">{row.error}</span>}
              {row.id && !row.verdict && !row.gaveUp && (
                <span className="inline-flex items-center gap-1.5 text-slate-400">
                  <LoaderCircle className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                  waiting or scanning
                </span>
              )}
              {row.gaveUp && <span className="text-slate-400">this scan didn't finish, try it on its own</span>}
              {row.id && row.verdict && (
                <>
                  <span className={VERDICT[row.verdict].tone}>
                    {VERDICT[row.verdict].label} · {row.score}/100
                  </span>
                  <button type="button" onClick={() => onOpen(row.id!)} className="text-blue-300 underline-offset-4 hover:text-blue-200 hover:underline">
                    Open report
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}

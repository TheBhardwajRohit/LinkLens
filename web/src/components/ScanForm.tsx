import { CircleAlert, LoaderCircle, ScanSearch, ShieldCheck } from "lucide-react";
import { useEffect, useId, useState, type FormEvent, type RefObject } from "react";

import { getHealth, submitScan } from "../lib/api";
import { checkUrl, defang } from "../lib/url";

type Status =
  | { kind: "idle" }
  | { kind: "invalid"; error: string }
  | { kind: "sending" }
  | { kind: "accepted"; url: string; message: string; refanged: boolean }
  | { kind: "rejected"; error: string }
  | { kind: "offline" };

function ScannerPill({ online }: { online: boolean | null }) {
  const [dot, label] =
    online === null ? ["bg-slate-500", "Checking scanner"] : online ? ["bg-emerald-400", "Scanner online"] : ["bg-slate-500", "Scanner offline"];
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-line bg-ink/60 px-3 py-1 text-xs text-slate-400">
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      {label}
    </span>
  );
}

export default function ScanForm({ inputRef }: { inputRef: RefObject<HTMLInputElement | null> }) {
  const [value, setValue] = useState("");
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [online, setOnline] = useState<boolean | null>(null);
  const helpId = useId();
  const statusId = useId();

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal).then((h) => {
      if (!controller.signal.aborted) setOnline(h !== null);
    });
    return () => controller.abort();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const check = checkUrl(value);
    if (!check.ok) {
      setStatus({ kind: "invalid", error: check.error });
      return;
    }
    setStatus({ kind: "sending" });
    const result = await submitScan(check.url);
    if (result.kind === "accepted") {
      setStatus({ kind: "accepted", url: result.scan.url, message: result.scan.message, refanged: check.refanged });
      setOnline(true);
    } else if (result.kind === "rejected") {
      setStatus({ kind: "rejected", error: result.error });
    } else {
      setStatus({ kind: "offline" });
      setOnline(false);
    }
  }

  const error = status.kind === "invalid" || status.kind === "rejected" ? status.error : null;

  return (
    <section id="scan" className="relative mx-auto max-w-3xl scroll-mt-24 px-4 pb-28 pt-8 sm:pb-36">
      <div className="rounded-3xl border border-cyan-300/15 bg-panel/80 p-6 shadow-[0_40px_120px_-40px_rgba(34,211,238,0.35)] backdrop-blur-md sm:p-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-2xl font-semibold text-white sm:text-3xl">Scan a link</h2>
          <ScannerPill online={online} />
        </div>
        <p id={helpId} className="mt-3 text-slate-400">
          Paste any link you don't trust. We open it in a locked-down sandbox, so you never have to. Defanged links like{" "}
          <code className="font-mono text-sm text-slate-300">hxxp://example[.]com</code> work too.
        </p>

        <form onSubmit={onSubmit} noValidate className="mt-6 flex flex-col gap-3 sm:flex-row">
          <label htmlFor="scan-url" className="sr-only">
            Link to scan
          </label>
          <input
            ref={inputRef}
            id="scan-url"
            type="text"
            inputMode="url"
            autoComplete="off"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            placeholder="https://suspicious-site.example/login"
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              if (status.kind === "invalid" || status.kind === "rejected") setStatus({ kind: "idle" });
            }}
            aria-invalid={error ? true : undefined}
            aria-describedby={`${helpId} ${statusId}`}
            className={`min-w-0 flex-1 rounded-xl border bg-ink/80 px-4 py-3.5 font-mono text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:ring-2 ${
              error ? "border-rose-500/60 focus:ring-rose-500/40" : "border-line focus:border-cyan-400/50 focus:ring-cyan-400/30"
            }`}
          />
          <button
            type="submit"
            disabled={status.kind === "sending"}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-cyan-400 px-6 py-3.5 font-semibold text-ink transition hover:bg-cyan-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300 disabled:cursor-wait disabled:opacity-70"
          >
            {status.kind === "sending" ? (
              <LoaderCircle className="h-5 w-5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
            ) : (
              <ScanSearch className="h-5 w-5" aria-hidden="true" />
            )}
            Scan
          </button>
        </form>

        <div id={statusId} aria-live="polite" className="mt-4 min-h-6 text-sm">
          {error && (
            <p className="flex items-start gap-2 text-rose-300">
              <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              {error}
            </p>
          )}
          {status.kind === "offline" && (
            <p className="flex items-start gap-2 text-slate-300">
              <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" aria-hidden="true" />
              The scanner isn't online right now. LinkLens is still being built, and scanning only runs on a local machine for now.
            </p>
          )}
          {status.kind === "accepted" && (
            <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/5 p-4">
              <p className="flex items-center gap-2 font-medium text-emerald-300">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                Link received
              </p>
              <p className="mt-2 break-all font-mono text-slate-300">{defang(status.url)}</p>
              {status.refanged && <p className="mt-2 text-slate-400">We turned the defanged link back into a normal one first.</p>}
              <p className="mt-2 text-slate-400">{status.message}</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

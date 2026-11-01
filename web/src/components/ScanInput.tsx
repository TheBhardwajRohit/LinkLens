import { ArrowDown, ArrowRight, Check, CircleAlert, Link2, LoaderCircle, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type RefObject } from "react";

import type { Step } from "../lib/api";
import type { ScanControl } from "../lib/useScan";

/** The live checklist while a scan runs: each step ticks off as the server reports it. */
function StepList({ steps, startedAt }: { steps: Step[]; startedAt: number }) {
  if (steps.length === 0) {
    return <p className="text-slate-200">Starting the scan...</p>;
  }
  return (
    <ol className="space-y-2">
      {steps.map((step) => (
        <li key={step.id} className="flex items-center gap-2.5">
          <span className="flex h-5 w-5 items-center justify-center" aria-hidden="true">
            {step.status === "done" && <Check className="h-4 w-4 text-blue-400" />}
            {step.status === "running" && (
              <LoaderCircle className="h-4 w-4 animate-spin text-blue-300 motion-reduce:animate-none" />
            )}
            {step.status === "failed" && <X className="h-4 w-4 text-amber-300" />}
            {step.status === "pending" && <span className="h-1.5 w-1.5 rounded-full bg-slate-500" />}
          </span>
          <span className={step.status === "pending" ? "text-slate-400" : "text-slate-100"}>{step.label}</span>
          {step.status === "running" && (
            <span className="text-sm tabular-nums text-slate-400">
              <Elapsed since={startedAt} />
            </span>
          )}
          <span className="sr-only">{step.status}</span>
        </li>
      ))}
    </ol>
  );
}

function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return <>{Math.max(0, Math.round((now - since) / 1000))} s</>;
}

function ScannerStatus({ online }: { online: boolean | null }) {
  const [dot, label] =
    online === null
      ? ["bg-slate-500", "Checking the scanner"]
      : online
        ? ["bg-emerald-400", "Scanner online"]
        : ["bg-slate-500", "Scanner offline"];
  return (
    <span className="inline-flex items-center gap-2 text-sm text-slate-300">
      <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden="true" />
      {label}
    </span>
  );
}

// Harmless links that show what a report looks like. None of them is a real scam page: the first is
// a reserved example site, the second is Google's own test address (never a real site), and the
// third points at this machine, which the sandbox refuses to visit.
const EXAMPLES = [
  { label: "A safe site", url: "https://example.com" },
  { label: "A blacklisted test link", url: "http://malware.testing.google.test/testing/malware/" },
  { label: "A private address", url: "http://localtest.me" },
];

const QUIET_BUTTON =
  "inline-flex items-center gap-1.5 rounded-full bg-white/[0.07] px-3.5 py-1.5 text-sm text-slate-100 transition-[background-color,transform] duration-150 hover:bg-white/[0.12] active:scale-[0.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300 disabled:cursor-wait disabled:opacity-60";

/** The scanner's own control: the link field, its live status, and harmless examples. */
export default function ScanInput({
  scan,
  inputRef,
  value,
  onValueChange,
  initialUrl = null,
  onShowReport,
}: {
  scan: ScanControl;
  inputRef: RefObject<HTMLInputElement | null>;
  value: string;
  onValueChange: (value: string) => void;
  /** A link handed over from the homepage: checked once, on arrival. */
  initialUrl?: string | null;
  onShowReport: () => void;
}) {
  const { state, online } = scan;
  const statusId = useId();
  const started = useRef(false);
  const sending = state.kind === "sending";
  const error = state.kind === "invalid" || state.kind === "rejected" ? state.error : null;

  useEffect(() => {
    if (initialUrl && !started.current) {
      started.current = true;
      scan.submit(initialUrl);
    }
  }, [initialUrl, scan]);

  return (
    <div data-ui className="mt-8 w-full max-w-xl">
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          if (!sending) scan.submit(value);
        }}
        className="flex flex-col gap-2 rounded-2xl bg-panel p-2 ring-1 ring-white/10 sm:flex-row"
      >
        <label htmlFor="scan-url" className="sr-only">
          Link to check
        </label>
        <div
          className={`flex min-w-0 flex-1 items-center gap-2.5 rounded-xl px-3 transition-[background-color,box-shadow] duration-150 focus-within:bg-white/[0.04] focus-within:ring-2 ${
            error ? "ring-1 ring-rose-400/60 focus-within:ring-rose-400/60" : "focus-within:ring-blue-400"
          }`}
        >
          <Link2 className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
          <input
            ref={inputRef}
            id="scan-url"
            type="text"
            inputMode="url"
            autoComplete="off"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            placeholder="Paste a suspicious link"
            value={value}
            onChange={(e) => {
              onValueChange(e.target.value);
              scan.clearError();
            }}
            aria-invalid={error ? true : undefined}
            aria-describedby={statusId}
            className="min-w-0 flex-1 bg-transparent py-3.5 text-base text-slate-100 placeholder:text-slate-400 focus:outline-none"
          />
        </div>
        <button
          type="submit"
          disabled={sending}
          className="inline-flex h-[52px] items-center justify-center gap-2 rounded-xl bg-blue-600 px-6 text-base font-semibold text-white transition-[background-color,transform] duration-150 hover:bg-blue-500 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300 disabled:cursor-wait disabled:opacity-85"
        >
          {sending ? "Checking" : "Check it"}
          {sending ? (
            <LoaderCircle className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
          ) : (
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </form>

      <div id={statusId} aria-live="polite" className="mt-4 text-[15px]">
        {error && (
          <p className="flex items-start gap-2 text-rose-300">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            {error}
          </p>
        )}
        {sending && <StepList steps={state.steps} startedAt={state.startedAt} />}
        {state.kind === "loading" && (
          <p className="flex items-center gap-2 text-slate-200">
            <LoaderCircle className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
            Opening the saved scan...
          </p>
        )}
        {state.kind === "done" && (
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-slate-200">
            {state.example ? "Example report." : state.reopened ? "Saved scan." : "Scan finished."}
            {state.refanged && <span className="text-slate-400">We turned the broken link back into a normal one.</span>}
            <button
              type="button"
              onClick={onShowReport}
              className="inline-flex items-center gap-1 font-medium text-blue-300 underline-offset-4 hover:text-blue-200 hover:underline focus-visible:outline-2 focus-visible:outline-blue-300"
            >
              See the report <ArrowDown className="h-4 w-4" aria-hidden="true" />
            </button>
          </p>
        )}
        {state.kind === "unavailable" && (
          <p className="flex items-start gap-2 text-slate-200">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
            {state.error}
          </p>
        )}
        {state.kind === "offline" && (
          <p className="flex items-start gap-2 text-slate-200">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
            The scanner isn't online right now. It runs on a local install until a public scan server is set up.
          </p>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-3">
        <ScannerStatus online={online} />
        {online === false && state.kind !== "done" && state.kind !== "loading" && (
          <button type="button" onClick={() => scan.showExample().then(() => window.setTimeout(onShowReport, 60))} className={QUIET_BUTTON}>
            See an example report <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        )}
      </div>

      {online && (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-slate-300">Try a harmless example:</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex.url}
              type="button"
              disabled={sending}
              onClick={() => {
                onValueChange(ex.url);
                scan.submit(ex.url);
              }}
              className={QUIET_BUTTON}
            >
              {ex.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

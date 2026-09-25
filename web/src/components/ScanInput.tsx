import { ArrowDown, ArrowRight, Check, CircleAlert, Link2, LoaderCircle, X } from "lucide-react";
import { useEffect, useId, useState, type RefObject } from "react";

import type { Step } from "../lib/api";
import type { ScanControl } from "../lib/useScan";

/** The live checklist while a scan runs: each step ticks off as the server reports it. */
function StepList({ steps, startedAt }: { steps: Step[]; startedAt: number }) {
  if (steps.length === 0) {
    return <p className="text-slate-300">Starting the scan...</p>;
  }
  return (
    <ol className="space-y-1.5">
      {steps.map((step) => (
        <li key={step.id} className="flex items-center gap-2.5">
          <span className="flex h-5 w-5 items-center justify-center" aria-hidden="true">
            {step.status === "done" && <Check className="h-4 w-4 text-blue-400" />}
            {step.status === "running" && (
              <LoaderCircle className="h-4 w-4 animate-spin text-blue-300 motion-reduce:animate-none" />
            )}
            {step.status === "failed" && <X className="h-4 w-4 text-amber-300" />}
            {step.status === "pending" && <span className="h-1.5 w-1.5 rounded-full bg-slate-600" />}
          </span>
          <span className={step.status === "pending" ? "text-slate-500" : "text-slate-200"}>{step.label}</span>
          {step.status === "running" && (
            <span className="font-mono text-xs text-slate-500">
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

function ScannerPill({ online }: { online: boolean | null }) {
  const [dot, label] =
    online === null
      ? ["bg-slate-500", "Checking scanner"]
      : online
        ? ["bg-emerald-400", "Scanner online"]
        : ["bg-slate-500", "Scanner offline"];
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}

const TRUST = ["Isolated sandbox", "Never downloads files", "Private addresses blocked"];

export default function ScanInput({
  scan,
  inputRef,
  onShowReport,
}: {
  scan: ScanControl;
  inputRef: RefObject<HTMLInputElement | null>;
  onShowReport: () => void;
}) {
  const [value, setValue] = useState("");
  const { state, online } = scan;
  const statusId = useId();
  const sending = state.kind === "sending";
  const error = state.kind === "invalid" || state.kind === "rejected" ? state.error : null;

  return (
    <div className="mt-9 max-w-xl">
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          if (!sending) scan.submit(value);
        }}
        className="flex flex-col gap-2.5 sm:flex-row"
      >
        <label htmlFor="scan-url" className="sr-only">
          Link to scan
        </label>
        <div
          className={`flex min-w-0 flex-1 items-center gap-2.5 rounded-xl border bg-white/[0.045] pl-2 pr-3 backdrop-blur-md transition focus-within:bg-white/[0.07] focus-within:ring-4 ${
            error
              ? "border-rose-400/60 focus-within:ring-rose-500/15"
              : "border-white/15 focus-within:border-blue-400/60 focus-within:ring-blue-500/15"
          }`}
        >
          <span
            aria-hidden="true"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/[0.07] text-slate-300 ring-1 ring-white/10"
          >
            <Link2 className="h-4 w-4" />
          </span>
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
              setValue(e.target.value);
              scan.clearError();
            }}
            aria-invalid={error ? true : undefined}
            aria-describedby={statusId}
            className="min-w-0 flex-1 bg-transparent py-3.5 font-mono text-sm text-slate-100 placeholder:font-sans placeholder:text-slate-500 focus:outline-none"
          />
        </div>
        <button
          type="submit"
          disabled={sending}
          className="inline-flex items-center justify-center gap-2.5 rounded-xl bg-linear-to-b from-blue-500 to-blue-600 px-5 py-3.5 font-semibold text-white shadow-[0_12px_32px_-12px_rgba(59,130,246,0.95)] ring-1 ring-inset ring-white/15 transition hover:from-blue-400 hover:to-blue-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300 disabled:cursor-wait disabled:opacity-85"
        >
          {sending ? "Scanning" : "Scan link"}
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white text-blue-600">
            {sending ? (
              <LoaderCircle className="h-3 w-3 animate-spin motion-reduce:animate-none" aria-hidden="true" />
            ) : (
              <ArrowRight className="h-3 w-3" aria-hidden="true" />
            )}
          </span>
        </button>
      </form>

      <div id={statusId} aria-live="polite" className="mt-3 min-h-5 text-sm">
        {error && (
          <p className="flex items-start gap-2 text-rose-300">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            {error}
          </p>
        )}
        {sending && <StepList steps={state.steps} startedAt={state.startedAt} />}
        {state.kind === "loading" && (
          <p className="flex items-center gap-2 text-slate-300">
            <LoaderCircle className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
            Opening the saved scan...
          </p>
        )}
        {state.kind === "done" && (
          <p className="flex flex-wrap items-center gap-x-2 text-slate-300">
            {state.reopened ? "Saved scan." : "Scan finished."}
            {state.refanged && <span className="text-slate-400">(We turned the defanged link back into a normal one.)</span>}
            <button
              type="button"
              onClick={onShowReport}
              className="inline-flex items-center gap-1 font-medium text-blue-300 underline-offset-4 hover:text-blue-200 hover:underline"
            >
              See the full report <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </p>
        )}
        {state.kind === "unavailable" && (
          <p className="flex items-start gap-2 text-slate-300">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" aria-hidden="true" />
            {state.error}
          </p>
        )}
        {state.kind === "offline" && (
          <p className="flex items-start gap-2 text-slate-300">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" aria-hidden="true" />
            The scanner isn't online right now. LinkLens is still being built, and scanning only runs on a local
            machine for now.
          </p>
        )}
      </div>

      <ul className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-400">
        <li>
          <ScannerPill online={online} />
        </li>
        {TRUST.map((item) => (
          <li key={item} className="inline-flex items-center gap-1.5">
            <Check className="h-3.5 w-3.5 text-blue-400" aria-hidden="true" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

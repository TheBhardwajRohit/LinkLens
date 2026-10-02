// What you can do with a report: copy its link, save it as a PDF, report a mistake, scan another.

import { Check, Copy, FileDown, Flag, RotateCcw } from "lucide-react";
import { useId, useState } from "react";

import { sendFeedback, type FeedbackKind } from "../lib/api";
import { resultLink } from "../lib/useScan";

const BUTTON =
  "inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm ring-1 transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300";
const QUIET = `${BUTTON} text-slate-300 ring-white/10 hover:text-white hover:ring-white/30`;
const SOLID = `${BUTTON} bg-white/[0.06] text-slate-100 ring-white/10 hover:bg-white/10`;
const PRIMARY = `${BUTTON} bg-blue-600 font-medium text-white ring-blue-400/40 hover:bg-blue-500 disabled:opacity-70`;

const KINDS: { kind: FeedbackKind; label: string }[] = [
  { kind: "false_alarm", label: "The site is fine, but LinkLens flagged it" },
  { kind: "missed_scam", label: "The site is a scam, but LinkLens missed it" },
  { kind: "other", label: "Something else is wrong" },
];

/** Opens every folded section of the report, prints, then folds them back. The browser's print
 * dialog has "Save as PDF", so this is also the PDF download. */
function printReport() {
  const folded = [...document.querySelectorAll<HTMLDetailsElement>("#report details:not([open])")];
  folded.forEach((d) => (d.open = true));
  const restore = () => {
    folded.forEach((d) => (d.open = false));
    window.removeEventListener("afterprint", restore);
  };
  window.addEventListener("afterprint", restore);
  window.print();
}

function MistakeForm({ id, onDone }: { id: string; onDone: () => void }) {
  const [kind, setKind] = useState<FeedbackKind>("false_alarm");
  const [note, setNote] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "failed">("idle");
  const [error, setError] = useState("");
  const group = useId();

  if (state === "sent") {
    return (
      <p className="mt-4 rounded-xl border border-white/[0.08] bg-ink/40 px-4 py-3 text-sm text-slate-200" role="status">
        Thanks. Your report is saved with this scan and will be looked at. The verdict doesn't change by itself.
      </p>
    );
  }
  return (
    <form
      className="mt-4 rounded-xl border border-white/[0.08] bg-ink/40 p-4 text-sm"
      onSubmit={async (e) => {
        e.preventDefault();
        setState("sending");
        const result = await sendFeedback(id, kind, note);
        if (result.ok) setState("sent");
        else {
          setError(result.error);
          setState("failed");
        }
      }}
    >
      <fieldset>
        <legend className="font-medium text-cream">What did LinkLens get wrong?</legend>
        <div className="mt-2 space-y-1.5">
          {KINDS.map((k) => (
            <label key={k.kind} className="flex items-center gap-2 text-slate-200">
              <input type="radio" name={group} checked={kind === k.kind} onChange={() => setKind(k.kind)} className="accent-blue-500" />
              {k.label}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="mt-3 block text-slate-300">
        Anything to add? (optional)
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={500}
          rows={2}
          className="mt-1 block w-full rounded-lg border border-white/15 bg-white/[0.04] px-3 py-2 text-slate-100 placeholder:text-slate-500 focus:border-blue-400/60 focus:outline-none"
          placeholder="For example: this is my own shop's site"
        />
      </label>
      <p className="mt-1 text-xs text-slate-500">Don't include personal details. Email addresses are removed before saving.</p>
      {state === "failed" && <p className="mt-2 text-rose-300">{error}</p>}
      <div className="mt-3 flex gap-2">
        <button type="submit" disabled={state === "sending"} className={PRIMARY}>
          {state === "sending" ? "Sending" : "Send report"}
        </button>
        <button type="button" onClick={onDone} className={QUIET}>
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function ReportActions({ id, saved, onScanAnother }: { id: string; saved: boolean; onScanAnother: () => void }) {
  const [copied, setCopied] = useState(false);
  const [reporting, setReporting] = useState(false);
  return (
    <div className="print:hidden">
      <div className="flex flex-wrap gap-2">
        {saved && (
          <button
            type="button"
            onClick={() => {
              navigator.clipboard
                ?.writeText(resultLink(id))
                .then(() => {
                  setCopied(true);
                  window.setTimeout(() => setCopied(false), 1800);
                })
                .catch(() => {});
            }}
            className={SOLID}
          >
            {copied ? <Check className="h-4 w-4 text-emerald-300" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
            {copied ? "Link copied" : "Copy link to this result"}
          </button>
        )}
        <button type="button" onClick={printReport} className={SOLID} title="Opens the print window. Choose 'Save as PDF' there.">
          <FileDown className="h-4 w-4" aria-hidden="true" />
          Download report (PDF)
        </button>
        <button type="button" onClick={() => setReporting((v) => !v)} aria-expanded={reporting} className={QUIET}>
          <Flag className="h-4 w-4" aria-hidden="true" />
          Report a mistake
        </button>
        <button type="button" onClick={onScanAnother} className={QUIET}>
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          Scan another link
        </button>
      </div>
      {reporting && <MistakeForm id={id} onDone={() => setReporting(false)} />}
    </div>
  );
}

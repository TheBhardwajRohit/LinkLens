import { RotateCcw } from "lucide-react";
import type { Ref } from "react";

import type { Scan } from "../lib/api";
import VisitReport from "./VisitReport";

export default function ScanResults({
  scan,
  sectionRef,
  onScanAnother,
}: {
  scan: Scan;
  sectionRef: Ref<HTMLElement>;
  onScanAnother: () => void;
}) {
  return (
    <section id="report" ref={sectionRef} className="mx-auto max-w-4xl scroll-mt-6 px-4 pt-20 sm:px-6">
      <div className="rounded-3xl border border-white/[0.08] bg-panel/90 p-6 shadow-[0_40px_120px_-40px_rgba(59,130,246,0.35)] backdrop-blur-md sm:p-10">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-2xl font-medium tracking-tight text-cream sm:text-3xl">Scan report</h2>
          <button
            type="button"
            onClick={onScanAnother}
            className="inline-flex items-center gap-2 rounded-lg border border-white/15 px-3 py-1.5 text-sm text-slate-200 transition hover:border-white/40 hover:text-white"
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            Scan another link
          </button>
        </div>
        <VisitReport visit={scan.visit} />
      </div>
    </section>
  );
}

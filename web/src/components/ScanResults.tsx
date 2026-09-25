import type { Ref } from "react";

import type { Scan } from "../lib/api";
import { formatDate } from "../lib/format";
import { ComingSoon, ResultActions, VerdictCard, WhyFlagged } from "./Verdict";
import VisitReport from "./VisitReport";

// Report order follows the plan: verdict, screenshot, who's behind it, link trail, reasons,
// later-phase features, then actions.
export default function ScanResults({
  scan,
  reopened,
  sectionRef,
  onScanAnother,
}: {
  scan: Scan;
  reopened: boolean;
  sectionRef: Ref<HTMLElement>;
  onScanAnother: () => void;
}) {
  return (
    <section id="report" ref={sectionRef} className="mx-auto max-w-4xl scroll-mt-6 px-4 pt-20 sm:px-6">
      <div className="rounded-3xl border border-white/[0.08] bg-panel/90 p-6 shadow-[0_40px_120px_-40px_rgba(59,130,246,0.35)] backdrop-blur-md sm:p-10">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-display text-2xl font-medium tracking-tight text-cream sm:text-3xl">Scan report</h2>
            {reopened && (
              <p className="mt-1 text-sm text-slate-500">
                Saved scan from {formatDate(scan.created_at)}. Personal details in the link were removed before saving.
              </p>
            )}
          </div>
          <ResultActions id={scan.id} saved={scan.saved} onScanAnother={onScanAnother} />
        </div>
        <div className="space-y-6">
          <VerdictCard analysis={scan.analysis} />
          <VisitReport visit={scan.visit} recon={scan.recon} />
          <WhyFlagged analysis={scan.analysis} />
          <ComingSoon />
        </div>
      </div>
    </section>
  );
}

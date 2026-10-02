import type { Ref } from "react";

import type { Scan } from "../lib/api";
import { formatDate } from "../lib/format";
import BlacklistReport from "./BlacklistReport";
import { FamilyCard, SiblingTabs } from "./FamilyReport";
import Guard from "./Guard";
import NetworkMap from "./NetworkMap";
import { ComingSoon, ResultActions, VerdictCard, WhyFlagged } from "./Verdict";
import { VisitDetails, VisitSummary } from "./VisitReport";

// Report order follows the plan: verdict, screenshot, family, siblings, network map, who's
// behind it (with the server map), link trail, reasons, blacklist results, then actions. Each part is guarded,
// so an old or incomplete saved scan can't blank the whole page.
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
        <div className="space-y-6" key={scan.id}>
          <Guard name="verdict">
            <VerdictCard analysis={scan.analysis} />
          </Guard>
          <Guard name="page preview">
            <VisitSummary visit={scan.visit} />
          </Guard>
          <Guard name="scam family">
            <FamilyCard family={scan.family} />
          </Guard>
          <Guard name="sibling sites">
            <SiblingTabs siblings={scan.siblings} family={scan.family} />
          </Guard>
          <Guard name="network map">
            <NetworkMap graph={scan.graph} />
          </Guard>
          <Guard name="page details">
            <VisitDetails visit={scan.visit} recon={scan.recon} />
          </Guard>
          <Guard name="reasons">
            <WhyFlagged analysis={scan.analysis} />
          </Guard>
          <Guard name="blacklist results">
            <BlacklistReport blacklists={scan.blacklists} />
          </Guard>
          <ComingSoon />
        </div>
      </div>
    </section>
  );
}

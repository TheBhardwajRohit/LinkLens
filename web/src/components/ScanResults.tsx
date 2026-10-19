import { useState, type ReactNode, type Ref } from "react";

import type { Scan } from "../lib/api";
import { formatDate } from "../lib/format";
import { defang } from "../lib/url";
import { resultLink } from "../lib/useScan";
import BlacklistReport from "./BlacklistReport";
import { FamilyCard, SiblingTabs } from "./FamilyReport";
import Guard from "./Guard";
import NetworkMap from "./NetworkMap";
import ReportActions from "./ReportActions";
import { Advice, KeyFacts, WarnFamily } from "./ReportSummary";
import { VerdictCard, WhyFlagged } from "./Verdict";
import { VisitDetails, VisitSummary } from "./VisitReport";

type View = "simple" | "full";
type TabId = "overview" | "behind" | "family";

const TABS: { id: TabId; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "behind", label: "Who's behind it" },
  { id: "family", label: "Family and siblings" },
];
const VIEW_KEY = "linklens-view";

function savedView(): View {
  try {
    return window.localStorage.getItem(VIEW_KEY) === "simple" ? "simple" : "full";
  } catch {
    return "full";
  }
}

function ViewSwitch({ view, onChange }: { view: View; onChange: (v: View) => void }) {
  const options: { id: View; label: string }[] = [
    { id: "simple", label: "Simple" },
    { id: "full", label: "Full report" },
  ];
  return (
    <div role="radiogroup" aria-label="How much detail to show" className="inline-flex rounded-lg bg-white/[0.05] p-1 ring-1 ring-white/10 print:hidden">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="radio"
          aria-checked={view === o.id}
          onClick={() => onChange(o.id)}
          className={`rounded-md px-3 py-1.5 text-sm transition focus-visible:outline-2 focus-visible:outline-blue-300 ${
            view === o.id ? "bg-blue-600 font-medium text-white" : "text-slate-300 hover:text-white"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** A tab's content. Hidden tabs stay in the page, so printing or saving as PDF still shows everything. */
function Panel({ active, children }: { active: boolean; children: ReactNode }) {
  return <div className={`space-y-8 ${active ? "" : "hidden print:block"}`}>{children}</div>;
}

// Reading order: verdict with its main reasons, what to do, the key facts, then the details.
// On wide screens the summary sits on the left and the details on the right; on phones everything
// stacks in that same order. Each part is guarded, so an old or incomplete saved scan
// can't blank the whole page.
export default function ScanResults({
  scan,
  reopened,
  example = false,
  sectionRef,
  onScanAnother,
}: {
  scan: Scan;
  reopened: boolean;
  example?: boolean;
  sectionRef: Ref<HTMLElement>;
  onScanAnother: () => void;
}) {
  const [view, setView] = useState<View>(savedView);
  const [tab, setTab] = useState<TabId>("overview");

  function changeView(next: View) {
    setView(next);
    try {
      window.localStorage.setItem(VIEW_KEY, next);
    } catch {
      // Private windows may refuse storage; the switch still works for this visit.
    }
  }

  return (
    <section id="report" ref={sectionRef} className="mx-auto max-w-7xl scroll-mt-6 px-4 pt-20 sm:px-6">
      <div className="rounded-3xl border border-white/[0.08] bg-panel/90 p-5 shadow-[0_40px_120px_-40px_rgba(59,130,246,0.35)] backdrop-blur-md sm:p-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-display text-2xl font-medium tracking-tight text-cream sm:text-3xl">Scan report</h2>
            <p className="mt-1 break-all font-mono text-sm text-slate-300">{defang(scan.url)}</p>
            {example ? (
              <p className="mt-1 max-w-2xl text-sm text-slate-300">
                Example report: a real scan of Google's harmless test address, saved so you can see what a report looks
                like while the scanner is offline.
              </p>
            ) : reopened && (
              <p className="mt-1 text-sm text-slate-400">
                Saved scan from {formatDate(scan.created_at)}. Personal details in the link were removed before saving.
              </p>
            )}
          </div>
          <ViewSwitch view={view} onChange={changeView} />
        </div>
        <div className="mb-6">
          <ReportActions id={scan.id} saved={scan.saved} onScanAnother={onScanAnother} />
        </div>
        {/* Only on paper or in the PDF: what was scanned and when. */}
        <p className="mb-4 hidden text-sm text-slate-300 print:block">
          LinkLens report for <span className="font-mono">{defang(scan.url)}</span>, scanned {formatDate(scan.created_at)}.
          Results are likely, not certain.
        </p>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-8" key={scan.id}>
          <div className="space-y-5">
            <Guard name="verdict">
              <VerdictCard analysis={scan.analysis} />
            </Guard>
            <Guard name="advice">
              <Advice verdict={scan.analysis.verdict} />
            </Guard>
            <Guard name="key facts">
              <KeyFacts scan={scan} />
            </Guard>
            <Guard name="warning to share">
              <WarnFamily scan={scan} reportLink={scan.saved ? resultLink(scan.id) : null} />
            </Guard>
          </div>

          <div className="min-w-0">
            {view === "simple" && (
              <div className="space-y-6 print:hidden">
                <Guard name="page preview">
                  <VisitSummary visit={scan.visit} />
                </Guard>
                <p className="text-sm text-slate-300">
                  This is the short version.{" "}
                  <button
                    type="button"
                    onClick={() => changeView("full")}
                    className="font-medium text-blue-300 underline-offset-4 hover:text-blue-200 hover:underline"
                  >
                    Show the full report
                  </button>{" "}
                  for every reason, who's behind the site, its scam family, and the blacklist results.
                </p>
              </div>
            )}

            <div className={view === "simple" ? "hidden print:block" : ""}>
              <div role="tablist" aria-label="Report sections" className="mb-6 flex flex-wrap gap-1 border-b border-white/[0.08] print:hidden">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    role="tab"
                    id={`tab-${t.id}`}
                    aria-selected={tab === t.id}
                    aria-controls={`panel-${t.id}`}
                    onClick={() => setTab(t.id)}
                    className={`-mb-px border-b-2 px-3.5 py-2.5 text-sm transition focus-visible:outline-2 focus-visible:outline-blue-300 ${
                      tab === t.id
                        ? "border-blue-400 font-medium text-cream"
                        : "border-transparent text-slate-300 hover:border-white/20 hover:text-white"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <div role="tabpanel" id="panel-overview" aria-labelledby="tab-overview" className="print:mb-8">
                <Panel active={tab === "overview"}>
                  <Guard name="page preview">
                    <VisitSummary visit={scan.visit} />
                  </Guard>
                  <Guard name="reasons">
                    <WhyFlagged analysis={scan.analysis} />
                  </Guard>
                  <Guard name="blacklist results">
                    <BlacklistReport blacklists={scan.blacklists} />
                  </Guard>
                </Panel>
              </div>
              <div role="tabpanel" id="panel-behind" aria-labelledby="tab-behind" className="print:mb-8">
                <Panel active={tab === "behind"}>
                  <Guard name="page details">
                    <VisitDetails
                      visit={scan.visit}
                      recon={scan.recon}
                      sharedHost={(scan.analysis.final_link ?? scan.analysis.link)?.free_hosting ?? null}
                    />
                  </Guard>
                </Panel>
              </div>
              <div role="tabpanel" id="panel-family" aria-labelledby="tab-family">
                <Panel active={tab === "family"}>
                  <Guard name="scam family">
                    <FamilyCard family={scan.family} />
                  </Guard>
                  <Guard name="sibling sites">
                    <SiblingTabs siblings={scan.siblings} family={scan.family} />
                  </Guard>
                  {/* Drawn again when the tab opens: a map drawn while hidden has no size to fit into. */}
                  <Guard name="network map" key={tab === "family" ? "map-shown" : "map-hidden"}>
                    <NetworkMap graph={scan.graph} />
                  </Guard>
                </Panel>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

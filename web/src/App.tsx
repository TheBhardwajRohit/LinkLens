import { useMemo, useRef } from "react";

import Features from "./components/Features";
import Footer from "./components/Footer";
import Hero from "./components/Hero";
import NavBar from "./components/NavBar";
import ProofStrip from "./components/ProofStrip";
import ScanInput from "./components/ScanInput";
import ScanResults from "./components/ScanResults";
import { EXAMPLE_MODEL, modelFromPreview, modelFromVisit, searchingModel, type GraphModel } from "./graph/model";
import { prefersReducedMotion } from "./lib/device";
import { useScan } from "./lib/useScan";

export default function App() {
  const scan = useScan();
  const inputRef = useRef<HTMLInputElement>(null);
  const reportRef = useRef<HTMLElement>(null);
  const lastModel = useRef<GraphModel>(EXAMPLE_MODEL);

  // The hero graph shows an example until a scan starts, grows as each step reports in, then shows
  // the result. The same graph is kept until its data really changes, so it doesn't restart.
  const model = useMemo(() => {
    const s = scan.state;
    let next: GraphModel = EXAMPLE_MODEL;
    if (s.kind === "sending") {
      next = s.id ? modelFromPreview(s.url, s.id, s.preview) : searchingModel(s.url, `searching-${s.startedAt}`);
    } else if (s.kind === "done") {
      const a = s.scan.analysis;
      next = modelFromVisit(s.scan.visit, `${s.scan.id}-scored`, s.scan.recon, { score: a.score, verdict: a.verdict });
    }
    if (next.key === lastModel.current.key) return lastModel.current;
    lastModel.current = next;
    return next;
  }, [scan.state]);

  const behavior = () => (prefersReducedMotion() ? "auto" : "smooth") as ScrollBehavior;

  function focusInput() {
    document.getElementById("top")?.scrollIntoView({ behavior: behavior() });
    window.setTimeout(() => inputRef.current?.focus({ preventScroll: true }), prefersReducedMotion() ? 0 : 500);
  }

  return (
    <>
      <div aria-hidden="true" className="page-bg" />
      <NavBar onScanClick={focusInput} />
      <main>
        <Hero model={model}>
          <ScanInput
            scan={scan}
            inputRef={inputRef}
            onShowReport={() => reportRef.current?.scrollIntoView({ behavior: behavior() })}
          />
        </Hero>
        <ProofStrip />
        {scan.state.kind === "done" && (
          <ScanResults
            scan={scan.state.scan}
            reopened={scan.state.reopened}
            sectionRef={reportRef}
            onScanAnother={focusInput}
          />
        )}
        <Features />
      </main>
      <Footer />
    </>
  );
}

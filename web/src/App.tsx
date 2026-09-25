import { useMemo, useRef } from "react";

import Features from "./components/Features";
import Footer from "./components/Footer";
import Hero from "./components/Hero";
import NavBar from "./components/NavBar";
import ProofStrip from "./components/ProofStrip";
import ScanInput from "./components/ScanInput";
import ScanResults from "./components/ScanResults";
import { EXAMPLE_MODEL, modelFromVisit, searchingModel } from "./graph/model";
import { prefersReducedMotion } from "./lib/device";
import { useScan } from "./lib/useScan";

export default function App() {
  const scan = useScan();
  const inputRef = useRef<HTMLInputElement>(null);
  const reportRef = useRef<HTMLElement>(null);

  // The hero graph shows an example until a scan starts, then the real result.
  const model = useMemo(() => {
    const s = scan.state;
    if (s.kind === "sending") return searchingModel(s.url, `searching-${s.startedAt}`);
    if (s.kind === "done") return modelFromVisit(s.scan.visit, s.scan.id);
    return EXAMPLE_MODEL;
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
          <ScanResults scan={scan.state.scan} sectionRef={reportRef} onScanAnother={focusInput} />
        )}
        <Features />
      </main>
      <Footer />
    </>
  );
}

import { useMemo, useRef, useState } from "react";

import BulkScan from "./components/BulkScan";
import DataHealth from "./components/DataHealth";
import Footer from "./components/Footer";
import Hero from "./components/Hero";
import NavBar from "./components/NavBar";
import ScanInput from "./components/ScanInput";
import ScanResults from "./components/ScanResults";
import Trends from "./components/Trends";
import { EXAMPLE_MODEL, modelFromPreview, modelFromVisit, searchingModel, type GraphModel } from "./graph/model";
import { prefersReducedMotion } from "./lib/device";
import { takeHandOff } from "./lib/pages";
import { useScan } from "./lib/useScan";

export default function App() {
  const scan = useScan();
  const inputRef = useRef<HTMLInputElement>(null);
  const reportRef = useRef<HTMLElement>(null);
  const lastModel = useRef<GraphModel>(EXAMPLE_MODEL);
  // A link typed on the homepage, checked as soon as this page opens.
  const [handedOff] = useState(takeHandOff);

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
            initialUrl={handedOff}
            onShowReport={() => reportRef.current?.scrollIntoView({ behavior: behavior() })}
          />
          <BulkScan
            online={scan.online}
            onOpen={(id) => {
              scan.open(id).then(() => reportRef.current?.scrollIntoView({ behavior: behavior() }));
            }}
          />
        </Hero>
        {scan.state.kind === "done" && (
          <ScanResults
            scan={scan.state.scan}
            reopened={scan.state.reopened}
            example={scan.state.example}
            sectionRef={reportRef}
            onScanAnother={focusInput}
          />
        )}
        <DataHealth online={scan.online} />
        <Trends online={scan.online} />
      </main>
      <Footer />
    </>
  );
}

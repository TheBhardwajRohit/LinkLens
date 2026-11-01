import { useMemo, useRef, useState } from "react";

import BulkScan from "./components/BulkScan";
import ScanInput from "./components/ScanInput";
import ScanResults from "./components/ScanResults";
import { EXAMPLE_MODEL, modelFromPreview, modelFromVisit, searchingModel, type GraphModel } from "./graph/model";
import { prefersReducedMotion } from "./lib/device";
import { takeHandOff } from "./lib/pages";
import { useScan } from "./lib/useScan";
import AnotherLink from "./scan/AnotherLink";
import BrandFigure from "./scan/BrandFigure";
import Knows from "./scan/Knows";
import { useLibrary } from "./scan/library";
import ScanHero from "./scan/ScanHero";
import YourLink from "./scan/YourLink";
import SiteFooter from "./site/SiteFooter";

// The scanner page. Built like the homepage: the scan box and live graph first, then the report when
// there is one, then what happens to a pasted link, what the library knows, and a last scan box.
export default function App() {
  const scan = useScan();
  const library = useLibrary(scan.online);
  const inputRef = useRef<HTMLInputElement>(null);
  const reportRef = useRef<HTMLElement>(null);
  const lastModel = useRef<GraphModel>(EXAMPLE_MODEL);
  // A link typed on the homepage, checked as soon as this page opens.
  const [handedOff] = useState(takeHandOff);
  const [link, setLink] = useState(handedOff ?? "");

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
  const showReport = () => reportRef.current?.scrollIntoView({ behavior: behavior() });

  function toTop(then?: () => void) {
    window.scrollTo({ top: 0, behavior: behavior() });
    window.setTimeout(() => {
      inputRef.current?.focus({ preventScroll: true });
      then?.();
    }, prefersReducedMotion() ? 0 : 450);
  }

  return (
    <>
      <main>
        <ScanHero model={model}>
          <ScanInput scan={scan} inputRef={inputRef} value={link} onValueChange={setLink} initialUrl={handedOff} onShowReport={showReport} />
          <BulkScan
            online={scan.online}
            onOpen={(id) => {
              scan.open(id).then(showReport);
            }}
          />
        </ScanHero>
        {scan.state.kind === "done" && (
          <ScanResults
            scan={scan.state.scan}
            reopened={scan.state.reopened}
            example={scan.state.example}
            sectionRef={reportRef}
            onScanAnother={() => toTop()}
          />
        )}
        <YourLink />
        <BrandFigure library={library} />
        <Knows library={library} onCheck={() => toTop()} />
        <AnotherLink
          onCheck={(url) => {
            setLink(url);
            toTop(() => scan.submit(url));
          }}
        />
      </main>
      <SiteFooter />
    </>
  );
}

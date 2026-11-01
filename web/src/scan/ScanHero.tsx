// The scanner's first screen, built like the homepage's: two tones split down the middle. Left, the
// headline and the scan box. Right, the live graph, which plays an example before a scan, grows
// while one runs, and draws the real result after. On phones the scan box comes first.

import type { CSSProperties, ReactNode } from "react";

import GraphPanel from "../graph/GraphPanel";
import type { GraphModel } from "../graph/model";
import SiteHeader from "../site/SiteHeader";

function caption(model: GraphModel): string | null {
  if (model.mode === "searching") return "The sandbox is opening the link.";
  if (model.mode === "example") return null; // the graph labels its own example
  return "This scan, drawn: each dot is a site the link reached. Red ones were blocked.";
}

export default function ScanHero({ model, children }: { model: GraphModel; children: ReactNode }) {
  const note = caption(model);
  return (
    <section className="relative grid min-h-[max(100svh,640px)] grid-cols-1 lg:grid-cols-2">
      <SiteHeader page="scanner" />

      <div id="top" className="flex scroll-mt-0 flex-col justify-end bg-ink px-5 pb-12 pt-28 sm:px-10 lg:pb-16">
        <h1 className="lines font-display text-[clamp(2.6rem,5.4vw,6rem)] font-semibold leading-[0.98] tracking-[-0.03em] text-cream">
          <span className="line">
            <span data-line style={{ "--i": 0 } as CSSProperties}>
              Paste it here.
            </span>
          </span>
          <span className="line">
            <span data-line style={{ "--i": 1 } as CSSProperties}>
              We'll open it.
            </span>
          </span>
        </h1>
        <div className="after-lines">
          <p className="mt-6 max-w-[46ch] text-xl leading-relaxed text-slate-200">
            LinkLens loads the link in a sealed browser on its own server, then shows you the verdict, every reason, and
            who is behind it. Nothing opens on your phone.
          </p>
          {children}
        </div>
      </div>

      <div className="relative min-h-[56svh] bg-panel lg:min-h-0">
        <GraphPanel model={model} />
        {note && (
          <p className="absolute bottom-4 left-4 right-4 max-w-sm text-[15px] text-slate-200 sm:bottom-8 sm:left-8" aria-live="polite">
            {note}
          </p>
        )}
      </div>
    </section>
  );
}

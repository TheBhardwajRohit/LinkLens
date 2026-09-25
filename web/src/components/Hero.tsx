import type { ReactNode } from "react";

import GraphPanel from "../graph/GraphPanel";
import type { GraphModel } from "../graph/model";

// 60/40 split: text and the scan box on the left, the live graph on the right.
// On phones the two stack, text first.
export default function Hero({ model, children }: { model: GraphModel; children: ReactNode }) {
  return (
    <section id="top" className="relative overflow-hidden">
      <div aria-hidden="true" className="hero-glow pointer-events-none absolute inset-0" />
      <div className="relative mx-auto grid min-h-[max(100svh,680px)] max-w-[88rem] grid-cols-1 items-center gap-4 px-5 pb-32 pt-28 sm:px-8 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:gap-0 lg:pb-40 lg:pt-24">
        <div className="relative z-10 max-w-2xl lg:pr-10">
          <h1 className="font-display text-[2.6rem] font-medium leading-[1.04] tracking-[-0.02em] text-cream sm:text-6xl xl:text-7xl">
            See who's really behind the link.
          </h1>
          <p className="mt-6 max-w-xl text-[15px] leading-relaxed text-slate-300/85 sm:text-base">
            Paste a suspicious link. LinkLens opens it in a locked-down sandbox and shows you where it really goes,
            what it looks like, and who it talks to. You never open it yourself.
          </p>
          {children}
        </div>
        <div className="relative h-[380px] sm:h-[460px] lg:-mr-8 lg:h-[640px] xl:-mr-16">
          <GraphPanel model={model} />
        </div>
      </div>
    </section>
  );
}

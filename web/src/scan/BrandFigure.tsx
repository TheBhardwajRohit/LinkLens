// "Which brand do they copy?": pick a brand, read how many scam pages in the library copy it.
// The figure is the library's own count (trends.brands), live or from the dated snapshot.

import { useState } from "react";

import { formatCount } from "../lib/format";
import { Reveal } from "../site/parts";
import { sourceLine, type Library } from "./library";

export default function BrandFigure({ library }: { library: Library }) {
  const brands = library.trends.brands.slice(0, 8);
  const [picked, setPicked] = useState(0);
  if (brands.length === 0) return null;
  const brand = brands[Math.min(picked, brands.length - 1)];

  return (
    <section aria-labelledby="brand-heading" className="flex flex-col bg-panel px-5 py-20 sm:px-10 lg:min-h-[88svh] lg:py-24">
      <Reveal>
        <h2 id="brand-heading" className="font-display text-[clamp(1.75rem,2.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.02em] text-cream">
          Which brand do they copy?
        </h2>
      </Reveal>
      <Reveal order={1} className="mt-7">
        <div data-ui role="radiogroup" aria-label="Brand" className="flex max-w-2xl flex-wrap gap-1.5 rounded-2xl bg-ink/60 p-1.5">
          {brands.map((b, i) => (
            <button
              key={b.brand}
              type="button"
              role="radio"
              aria-checked={i === picked}
              onClick={() => setPicked(i)}
              className={`rounded-xl px-3.5 py-2 text-[15px] transition-[background-color,color,transform] duration-150 active:scale-[0.97] focus-visible:outline-2 focus-visible:outline-blue-300 ${
                i === picked ? "bg-blue-600 font-medium text-white" : "text-slate-200 hover:bg-white/[0.07]"
              }`}
            >
              {b.brand}
            </button>
          ))}
        </div>
      </Reveal>

      <div className="mt-16 flex flex-1 flex-col justify-end gap-8 lg:mt-24 lg:flex-row lg:items-end lg:justify-between">
        <p className="font-display font-bold leading-[0.8] tracking-[-0.04em] text-cream" aria-live="polite">
          <span key={brand.brand} className="figure-in inline-block text-[clamp(7rem,19vw,20rem)] tabular-nums">
            {formatCount(brand.pages)}
          </span>
          <span className="ml-3 text-[clamp(1.75rem,2.6vw,2.5rem)] tracking-[-0.02em]">pages</span>
        </p>
        <p className="max-w-[32ch] text-[17px] leading-relaxed text-slate-200 lg:pb-3">
          Scam pages in the library that copy {brand.brand}, out of {formatCount(library.stats.pages)} pages LinkLens has
          fingerprinted. {sourceLine(library)}
        </p>
      </div>
    </section>
  );
}

// The close: the scanner's own first step, already open. Whatever is typed here is handed to the
// scanner page, which checks it straight away.

import { ArrowRight, Link2 } from "lucide-react";
import { useState } from "react";

import { handOff, SCANNER } from "../lib/pages";
import { Reveal } from "./parts";

type View = "simple" | "full";
const VIEW_KEY = "linklens-view"; // the same choice the report remembers

export default function CheckCta() {
  const [value, setValue] = useState("hxxps://sbi-kyc-update[.]example/verify");
  const [view, setView] = useState<View>("simple");

  return (
    <section aria-labelledby="cta-heading" className="grid gap-12 bg-blue-700 px-5 py-20 sm:px-10 lg:min-h-[90svh] lg:grid-cols-12 lg:items-center lg:py-24">
      <div className="lg:col-span-5 lg:self-end">
        <Reveal>
          <h2 id="cta-heading" className="font-display text-[clamp(2.6rem,5.4vw,6rem)] font-semibold leading-[0.92] tracking-[-0.035em] text-white">
            Got a link?
            <br />
            Check it.
          </h2>
        </Reveal>
        <Reveal order={1}>
          <p className="mt-6 max-w-[40ch] text-[17px] leading-relaxed text-white/90">
            The scanner opens and starts at once. In about a minute you get the verdict, the reasons, and who is behind
            the site.
          </p>
        </Reveal>
      </div>

      <Reveal order={2} className="lg:col-span-5 lg:col-start-7">
        <form
          data-ui
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            if (value.trim()) handOff(value.trim());
            try {
              window.localStorage.setItem(VIEW_KEY, view);
            } catch {
              // Not remembered; the report opens in its usual view.
            }
            window.location.href = SCANNER;
          }}
          className="w-full max-w-[440px] rounded-2xl bg-ink p-6 ring-1 ring-white/10"
        >
          <p className="font-display text-xl font-semibold text-cream">Check a link</p>
          <label htmlFor="cta-url" className="mt-4 block text-sm text-slate-300">
            Paste the link from the message
          </label>
          <div className="mt-1.5 flex items-center gap-2 rounded-xl bg-white/[0.05] px-3 ring-1 ring-white/15 focus-within:ring-2 focus-within:ring-blue-400">
            <Link2 className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
            <input
              id="cta-url"
              type="text"
              inputMode="url"
              autoComplete="off"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="min-w-0 flex-1 bg-transparent py-3 text-[15px] text-slate-100 placeholder:text-slate-400 focus:outline-none"
              placeholder="Paste a suspicious link"
            />
          </div>
          <p className="mt-4 text-sm text-slate-300" id="cta-view-label">
            Report
          </p>
          <div role="radiogroup" aria-labelledby="cta-view-label" className="mt-1.5 grid grid-cols-2 gap-1 rounded-xl bg-white/[0.05] p-1">
            {(["simple", "full"] as const).map((v) => (
              <button
                key={v}
                type="button"
                role="radio"
                aria-checked={view === v}
                onClick={() => setView(v)}
                className={`rounded-lg py-2 text-sm transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-blue-300 ${
                  view === v ? "bg-panel font-medium text-cream" : "text-slate-300 hover:text-white"
                }`}
              >
                {v === "simple" ? "Simple" : "Full report"}
              </button>
            ))}
          </div>
          <button
            type="submit"
            className="mt-6 inline-flex h-[52px] w-full items-center justify-center gap-2 rounded-xl bg-blue-600 text-base font-semibold text-white transition-[background-color,transform] duration-150 hover:bg-blue-500 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300"
          >
            Check it
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </form>
      </Reveal>
    </section>
  );
}

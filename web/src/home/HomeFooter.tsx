// The close of the homepage: two rows of tiles, the name set large, and the way into the scanner.

import { SCANNER } from "../lib/pages";

const REPO = "https://github.com/TheBhardwajRohit/LinkLens";

const TILE = "rounded-2xl bg-panel p-6";
const LINK = "transition-colors hover:text-blue-300 focus-visible:outline-2 focus-visible:outline-blue-300";

export default function HomeFooter() {
  return (
    <footer className="grid grid-cols-2 gap-1.5 p-2 lg:grid-cols-12 lg:gap-2 lg:p-3">
      <div className="order-1 col-span-2 flex min-h-[160px] items-center justify-center rounded-2xl bg-[#dfe6f1] lg:order-5 lg:col-span-8 lg:min-h-[320px]">
        <p className="font-display text-[clamp(3.5rem,9vw,9rem)] font-bold leading-none tracking-[-0.04em] text-[#0b1220]">LinkLens</p>
      </div>
      <a
        href={SCANNER}
        className="group order-2 col-span-2 flex min-h-[160px] flex-col justify-between rounded-2xl bg-blue-600 p-6 transition-colors hover:bg-blue-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300 lg:order-6 lg:col-span-4 lg:min-h-[320px]"
      >
        <span className="font-display text-2xl font-semibold leading-tight text-white">Check a link</span>
        <svg viewBox="0 0 48 48" className="h-12 w-12 self-end text-white transition-transform duration-200 group-hover:translate-x-1" aria-hidden="true">
          <path d="M8 24h30M26 12l12 12-12 12" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </a>

      <nav aria-label="Footer" className={`${TILE} order-3 lg:order-2 lg:col-span-3 lg:min-h-[220px]`}>
        <ul className="space-y-2 text-[17px] text-slate-200">
          <li>
            <a href={SCANNER} className={LINK}>
              Scanner
            </a>
          </li>
          <li>
            <a href="#how" className={LINK}>
              How a check works
            </a>
          </li>
          <li>
            <a href={`${REPO}/blob/main/docs/MODEL_REPORT.md`} target="_blank" rel="noopener noreferrer" className={LINK}>
              Model report
            </a>
          </li>
          <li>
            <a href={REPO} target="_blank" rel="noopener noreferrer" className={LINK}>
              Source on GitHub
            </a>
          </li>
        </ul>
      </nav>
      <div className={`${TILE} order-4 flex flex-col justify-between gap-4 lg:order-3 lg:col-span-2`}>
        <p className="text-[17px] text-slate-200">Lost money to a scam?</p>
        <p className="text-[17px] text-slate-200">
          Call <span className="font-display text-2xl font-semibold text-cream">1930</span> or report at{" "}
          <a href="https://cybercrime.gov.in" target="_blank" rel="noopener noreferrer" className={`font-medium text-blue-300 ${LINK}`}>
            cybercrime.gov.in
          </a>
        </p>
      </div>
      <div className={`${TILE} order-5 col-span-2 flex flex-col justify-between gap-6 lg:order-1 lg:col-span-4 lg:min-h-[220px]`}>
        <p className="font-display text-2xl leading-snug text-cream">A free student project. Results are likely, not certain.</p>
        <p className="text-sm leading-relaxed text-slate-400">
          This product includes GeoLite Data created by MaxMind, available from{" "}
          <a href="https://www.maxmind.com" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-slate-200">
            https://www.maxmind.com
          </a>
          .
        </p>
      </div>
      <div className={`${TILE} order-6 col-span-2 flex flex-col justify-end lg:order-4 lg:col-span-3`}>
        <p className="text-sm text-slate-400">Made by</p>
        <a href="https://github.com/TheBhardwajRohit" target="_blank" rel="noopener noreferrer" className={`text-xl text-cream ${LINK}`}>
          TheBhardwajRohit
        </a>
      </div>
    </footer>
  );
}

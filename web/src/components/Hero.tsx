import { ChevronDown, ScanSearch } from "lucide-react";

export default function Hero({ onScanClick }: { onScanClick: () => void }) {
  return (
    <section className="relative flex min-h-svh flex-col items-center justify-center px-4 text-center">
      <p className="mb-7 inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/5 px-3.5 py-1 text-xs font-medium tracking-wide text-cyan-100/90">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-rose-400 opacity-60 motion-reduce:hidden" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-rose-500" />
        </span>
        Scam link analyzer
      </p>

      <h1 className="font-display text-7xl font-bold tracking-tight sm:text-8xl md:text-9xl">
        <span className="bg-linear-to-b from-white via-cyan-100 to-cyan-400 bg-clip-text text-transparent drop-shadow-[0_0_40px_rgba(34,211,238,0.35)]">
          LinkLens
        </span>
      </h1>

      <p className="mt-6 max-w-xl text-lg text-slate-300 sm:text-2xl">Paste a link. See who's really behind it.</p>

      <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row sm:gap-4">
        <button
          type="button"
          onClick={onScanClick}
          className="inline-flex items-center gap-2 rounded-full bg-cyan-400 px-7 py-3 font-semibold text-ink shadow-[0_0_40px_-8px_rgba(34,211,238,0.7)] transition hover:bg-cyan-300 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-300"
        >
          <ScanSearch className="h-5 w-5" aria-hidden="true" />
          Scan a link
        </button>
        <a
          href="#features"
          className="rounded-full px-5 py-3 font-medium text-slate-300 transition hover:text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-300"
        >
          What it finds
        </a>
      </div>

      <a
        href="#features"
        aria-label="Scroll to the features"
        className="absolute bottom-8 text-slate-500 transition hover:text-slate-300 motion-safe:animate-bounce"
      >
        <ChevronDown className="h-6 w-6" aria-hidden="true" />
      </a>
    </section>
  );
}

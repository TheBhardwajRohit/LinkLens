import { Ban, Box, Route, ShieldX } from "lucide-react";

const TILES = [
  { icon: Box, label: "Isolated sandbox" },
  { icon: Route, label: "Every redirect traced" },
  { icon: ShieldX, label: "Private addresses blocked" },
  { icon: Ban, label: "Nothing downloaded" },
];

// The dark panel that overlaps the bottom of the hero.
export default function ProofStrip() {
  return (
    <section id="safety" className="relative z-10 mx-auto -mt-24 max-w-[88rem] scroll-mt-8 px-3 sm:px-5 lg:-mt-28">
      <div className="flex flex-col gap-8 rounded-3xl border border-white/[0.06] bg-panel px-6 py-8 shadow-[0_-20px_60px_-30px_rgba(0,0,0,0.8)] sm:px-10 sm:py-10 lg:flex-row lg:items-center lg:justify-between">
        <div className="max-w-xl">
          <p className="font-display text-3xl font-medium tracking-tight text-cream xl:text-4xl">
            “Never open a suspicious link again.”
          </p>
          <p className="mt-3 text-sm text-slate-400">
            LinkLens opens it for you, in a locked-down browser that can't reach anything private and never saves a
            file.
          </p>
        </div>
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:shrink-0">
          {TILES.map(({ icon: Icon, label }) => (
            <li
              key={label}
              className="flex h-28 w-full flex-col items-center justify-center gap-2.5 rounded-2xl border border-white/10 bg-white/[0.02] px-3 text-center text-sm font-medium text-slate-200 sm:w-36"
            >
              <Icon className="h-5 w-5 text-blue-400" aria-hidden="true" />
              {label}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

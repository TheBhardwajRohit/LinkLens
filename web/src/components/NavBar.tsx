import { ArrowRight, Moon, ScanSearch, Sun } from "lucide-react";
import { useState } from "react";

import { applyTheme, storedTheme, type Theme } from "../lib/theme";

const REPO = "https://github.com/TheBhardwajRohit/LinkLens";

function ThemeSwitch() {
  const [theme, setTheme] = useState<Theme>(storedTheme);
  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      onClick={() => {
        applyTheme(next);
        setTheme(next);
      }}
      aria-label={`Switch to the ${next} theme`}
      title={`Switch to the ${next} theme`}
      className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/15 text-slate-200 transition hover:bg-white/10 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300"
    >
      {theme === "dark" ? <Sun className="h-4 w-4" aria-hidden="true" /> : <Moon className="h-4 w-4" aria-hidden="true" />}
    </button>
  );
}

export default function NavBar({ onScanClick }: { onScanClick: () => void }) {
  return (
    <header className="absolute inset-x-0 top-0 z-30">
      <div className="mx-auto flex max-w-[88rem] items-center justify-between gap-4 px-5 py-5 sm:px-8">
        <div className="flex items-center gap-2.5">
          <a
            href="#top"
            className="inline-flex items-center gap-1.5 rounded-lg bg-white px-2.5 py-1.5 font-display text-[15px] font-bold tracking-tight text-blue-600 shadow-[0_8px_28px_-10px_rgba(59,130,246,0.9)] transition hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300"
          >
            <ScanSearch className="h-4 w-4" aria-hidden="true" />
            LinkLens
          </a>
          <nav
            aria-label="Main"
            className="hidden items-center gap-0.5 rounded-lg border border-white/10 bg-white/[0.06] p-1 text-sm text-slate-200 backdrop-blur md:flex"
          >
            <a href="#features" className="rounded-md px-3 py-1 transition hover:bg-white/10 hover:text-white">
              Features
            </a>
            <a href="#safety" className="rounded-md px-3 py-1 transition hover:bg-white/10 hover:text-white">
              How it stays safe
            </a>
            <a
              href={REPO}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-md px-3 py-1 transition hover:bg-white/10 hover:text-white"
            >
              GitHub
            </a>
          </nav>
        </div>
        <div className="flex items-center gap-2">
          <ThemeSwitch />
          <button
          type="button"
          onClick={onScanClick}
          className="group inline-flex items-center gap-2 rounded-lg border border-white/70 px-3.5 py-1.5 text-sm font-medium text-white transition hover:bg-white hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300"
        >
          Scan a link
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white text-ink transition group-hover:bg-ink group-hover:text-white">
            <ArrowRight className="h-3 w-3" aria-hidden="true" />
          </span>
        </button>
        </div>
      </div>
    </header>
  );
}

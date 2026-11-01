// The top bar every page shares: the name, a few links, and the theme switch. It sits over the
// first screen of each page in the same place, so moving between the pages feels like one site.

import { Moon, Sun } from "lucide-react";
import { useState } from "react";

import { COMPARE, HOME, SCANNER } from "../lib/pages";
import { applyTheme, storedTheme, type Theme } from "../lib/theme";

const REPO = "https://github.com/TheBhardwajRohit/LinkLens";

export function ThemeSwitch() {
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
      className="flex h-9 w-9 items-center justify-center rounded-full bg-white/[0.07] text-slate-200 transition-[background-color,transform] duration-150 hover:bg-white/[0.12] hover:text-white active:scale-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300"
    >
      {theme === "dark" ? <Sun className="h-4 w-4" aria-hidden="true" /> : <Moon className="h-4 w-4" aria-hidden="true" />}
    </button>
  );
}

const LINK = "transition-colors duration-150 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-300";

export default function SiteHeader({ page }: { page: "home" | "scanner" | "compare" }) {
  const onHome = page === "home";
  return (
    <header className="site-header absolute inset-x-0 top-0 z-20 flex items-center justify-between gap-4 px-5 py-5 sm:px-10">
      <a href={onHome ? "#top" : HOME} className={`font-display text-xl font-bold tracking-tight text-cream ${LINK}`}>
        LinkLens
      </a>
      <nav aria-label="Main" className="flex items-center gap-5 text-[15px] text-slate-200">
        <a href={onHome ? "#how" : `${HOME}#how`} className={`hidden sm:inline ${LINK}`}>
          How it works
        </a>
        <a
          href={COMPARE}
          aria-current={page === "compare" ? "page" : undefined}
          className={`hidden sm:inline ${page === "compare" ? "font-medium text-cream" : ""} ${LINK}`}
        >
          Compared
        </a>
        <a href={REPO} target="_blank" rel="noopener noreferrer" className={`hidden md:inline ${LINK}`}>
          GitHub
        </a>
        {page === "scanner" ? (
          <a href={SCANNER} aria-current="page" className={`font-medium text-cream ${LINK}`}>
            Scanner
          </a>
        ) : (
          <a href={SCANNER} className="font-medium text-blue-300 transition-colors duration-150 hover:text-blue-200 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-300">
            Scanner
          </a>
        )}
        <ThemeSwitch />
      </nav>
    </header>
  );
}

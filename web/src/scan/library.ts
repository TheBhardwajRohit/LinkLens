// What LinkLens knows: the page library's numbers and trends. Live from the scanner when it is
// online; otherwise a dated snapshot shipped with the site, so the live site (which has no scanner
// yet) still shows real numbers, labelled with the day they were taken.

import { useEffect, useState } from "react";

import { getStats, getTrends, type Stats, type Trends } from "../lib/api";
import snapshot from "./library-snapshot.json";

export type Library = {
  stats: Stats;
  trends: Trends;
  /** True when the numbers come from the running scanner. */
  live: boolean;
  /** The day the numbers stand for (today when live). */
  asOf: Date;
};

const SNAPSHOT: Library = {
  stats: snapshot.stats as unknown as Stats,
  trends: snapshot.trends as unknown as Trends,
  live: false,
  asOf: new Date(`${snapshot.taken}T12:00:00Z`),
};

export function useLibrary(online: boolean | null): Library {
  const [library, setLibrary] = useState<Library>(SNAPSHOT);

  useEffect(() => {
    if (!online) return;
    const controller = new AbortController();
    Promise.all([getStats(controller.signal), getTrends(controller.signal)]).then(([stats, trends]) => {
      if (controller.signal.aborted || !stats || !trends) return;
      setLibrary({ stats, trends, live: true, asOf: new Date() });
    });
    return () => controller.abort();
  }, [online]);

  return library;
}

/** "Live from the scanner" or "From a snapshot taken on 1 Nov 2026". */
export function sourceLine(library: Library): string {
  if (library.live) return "Live from the scanner's library.";
  const day = library.asOf.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
  return `From a snapshot of the library taken on ${day}.`;
}

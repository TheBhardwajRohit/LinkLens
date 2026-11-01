// The comparison page's data: one run of jobs/compare.py, where the same links went to VirusTotal,
// PhishTank, and LinkLens on the same evening. Every number on the page comes from here; only the
// short names and descriptions of the links are written by hand.

import type { Verdict } from "../lib/api";
import run from "./runs/harmless.json";

export type Flag = { engine: string; category: string; label: string | null };

export type VtReport = {
  known: boolean;
  stats?: { malicious: number; suspicious: number; harmless: number; undetected: number; timeout: number };
  engines?: number;
  flagged?: Flag[];
  categories?: string[];
  reputation?: number | null;
  votes?: { harmless?: number; malicious?: number };
  title?: string | null;
  final_url?: string | null;
  first_seen?: string | null;
  last_analysis?: string | null;
  refused?: string;
};

export type PhishTank = {
  status: "listed" | "not_listed" | "limit" | "error";
  phish_id?: number | null;
  verified?: boolean;
  valid?: boolean;
};

export type Reason = { text: string; points: number; area: string };

export type LinkLensResult = {
  score: number;
  own_score: number;
  verdict: Verdict;
  summary: string;
  scam_type: { label: string; brand: string | null } | null;
  reasons: Reason[];
  good_signs: Reason[];
  model: number | null;
  unicode_host: string | null;
  visit: { final_url: string | null; title: string | null; stopped: string | null; notes: string[]; blocked: { host: string; reason: string }[] };
  owner: {
    registrar: string | null;
    created: string | null;
    age_days: number | null;
    country: string | null;
    network: string | null;
    abuse_email: string | null;
    certs_first_seen: string | null;
    cert_count: number | null;
  };
  family: { status: string; note: string | null; library_size: number | null };
  siblings: { same_server: number; same_owner: number; same_design: number; lookalikes: number };
};

export type RunLink = {
  url: string;
  asked_at: string;
  phishtank: PhishTank;
  vt_before: VtReport;
  vt_after?: VtReport;
  linklens: LinkLensResult;
  shot?: string;
};

export const RUN = run as unknown as { made: string; asked_at: string; links: RunLink[] };

/** Short names and plain descriptions for the links, in the order the page shows them. */
const ABOUT: { url: string; name: string; what: string }[] = [
  {
    url: "https://www.xn--80ak6aa92e.com/",
    name: "Fake apple.com",
    what: '"apple.com" spelled with Cyrillic letters. A harmless security demo from 2017.',
  },
  {
    url: "http://sbi-kyc-update.example/verify",
    name: "Made-up SBI link",
    what: "A scam-shaped link we made up for this test. The name can never exist, so no list can know it.",
  },
  {
    url: "http://localtest.me/",
    name: "Points at your computer",
    what: "A public name that leads back to the computer opening it, a trick used to reach private devices.",
  },
  {
    url: "https://testsafebrowsing.appspot.com/s/phishing.html",
    name: "Google's phishing test",
    what: "A harmless page Google keeps on its own phishing list, for testing.",
  },
  {
    url: "https://secure.eicar.org/eicar.com.txt",
    name: "Antivirus test file",
    what: "The standard harmless file every antivirus program is built to flag.",
  },
  {
    url: "https://www.onlinesbi.sbi/",
    name: "SBI's real website",
    what: "State Bank of India's own site.",
  },
  {
    url: "https://example.com/",
    name: "example.com",
    what: "An ordinary safe page, run for documentation since 1995.",
  },
  {
    url: "http://malware.testing.google.test/testing/malware/",
    name: "Google's malware test",
    what: "A test address Google lists as malware. It doesn't lead to any real site.",
  },
];

export type Tested = RunLink & { name: string; what: string };

export const TESTED: Tested[] = ABOUT.map((about) => {
  const link = RUN.links.find((l) => l.url === about.url);
  if (!link) throw new Error(`No result for ${about.url}`);
  return { ...link, ...about };
});

export function byName(name: string): Tested {
  const found = TESTED.find((t) => t.name === name);
  if (!found) throw new Error(`No tested link named ${name}`);
  return found;
}

/** VirusTotal's own answer: its fresh analysis when it made one, otherwise what it already knew. */
export function vtReport(link: RunLink): VtReport {
  const after = link.vt_after;
  if (after && after.known && after.stats) return after;
  return link.vt_before;
}

export type VtAnswer = { count: string | null; line: string; note: string | null };

export function vtAnswer(link: RunLink): VtAnswer {
  const report = vtReport(link);
  const refused = link.vt_after?.refused ?? null;
  if (!report.known || !report.stats) {
    return refused
      ? { count: null, line: "Refused to analyse it", note: `VirusTotal's message: "${refused}".` }
      : { count: null, line: "Has never seen this link", note: null };
  }
  const engines = report.engines ?? 0;
  const { malicious, suspicious } = report.stats;
  const more = suspicious ? `${suspicious} more call it suspicious.` : null;
  const older = refused ? `It refused a fresh analysis ("${refused}"), so this is its older report.` : null;
  return {
    count: `${malicious} / ${engines}`,
    line: `security vendors flag it as malicious`,
    note: [more, older].filter(Boolean).join(" ") || null,
  };
}

/** VirusTotal's community score: the sum of its users' votes, which can disagree with its vendors. */
export function communityScore(link: RunLink): number | null {
  return vtReport(link).reputation ?? null;
}

export function phishTankAnswer(link: RunLink): { line: string; note: string } {
  const pt = link.phishtank;
  if (pt.status === "listed") {
    if (pt.verified && pt.valid) return { line: `Confirmed phish, report #${pt.phish_id}`, note: "Verified by its members." };
    return { line: `Reported, as #${pt.phish_id}`, note: "Never verified by its members." };
  }
  if (pt.status === "not_listed") return { line: "No record of this link", note: "Nobody has reported it." };
  return { line: "No answer", note: "The lookup didn't respond." };
}

/** Points that came from other services' lists, which LinkLens also asks. */
export function listPoints(result: LinkLensResult): number {
  return result.reasons.filter((r) => r.area === "blacklist").reduce((sum, r) => sum + r.points, 0);
}

export function sum(reasons: { points: number }[]): number {
  return reasons.reduce((total, r) => total + r.points, 0);
}

/** A reason's first clause, for the small board: "The model rates this page 97% likely to be a scam page." */
function brief(text: string): string {
  return text.split(/, mostly because| It has seen/)[0].replace(/\.?$/, ".");
}

export type Line = { points: number; text: string; quiet?: boolean };

/** LinkLens's score as a few lines that add up to it: its own top findings, then one line each for
 * the rest, other services' lists, and good signs. `raised` explains when a fixed rule lifted it. */
export function ledger(ll: LinkLensResult): { lines: Line[]; raised: string | null } {
  const own = ll.reasons.filter((r) => r.area !== "blacklist").sort((a, b) => b.points - a.points);
  const lines: Line[] = own.length
    ? own.slice(0, 3).map((r) => ({ points: r.points, text: brief(r.text) }))
    : ll.good_signs.map((r) => ({ points: r.points, text: r.text }));
  const rest = sum(own.slice(3));
  const fromLists = listPoints(ll);
  const good = own.length ? sum(ll.good_signs) : 0;
  if (rest) lines.push({ points: rest, text: "other small signs", quiet: true });
  if (fromLists) lines.push({ points: fromLists, text: "from other services' lists", quiet: true });
  if (good) lines.push({ points: good, text: "good signs", quiet: true });
  const added = Math.max(0, Math.min(100, sum(lines)));
  const raised =
    ll.score > added
      ? ll.visit.stopped === "blocked"
        ? `Raised to ${ll.score}: a link that leads to a private address is always at least suspicious.`
        : `Raised to ${ll.score}: when a list flags a link strongly, LinkLens never rates it lower than dangerous.`
      : null;
  return { lines, raised };
}

/** A negative number with a true minus sign: "−346". */
export function minus(n: number): string {
  return n < 0 ? `−${Math.abs(n)}` : `${n}`;
}

/** The run's date in words, as India sees it. */
export function runDate(): string {
  return new Date(RUN.asked_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Kolkata" });
}

const shots = import.meta.glob<string>("./shots/*.jpg", { eager: true, import: "default", query: "?url" });

export function shotUrl(link: RunLink): string | null {
  return link.shot ? (shots[`./shots/${link.shot}`] ?? null) : null;
}

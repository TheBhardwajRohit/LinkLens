// The live comparison in the report: it shows each service's answer as the scanner returned it,
// says plainly when a service had nothing, and never shows OpenPhish data.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { Analysis, Comparison } from "../lib/api";
import CompareReport from "./CompareReport";

const ANALYSIS = {
  score: 70,
  verdict: "dangerous",
  summary: "This looks like a fake SBI banking page.",
  scam_type: null,
  reasons: [
    { text: "The address imitates SBI.", points: 30, area: "link" },
    { text: "VirusTotal flags it.", points: 60, area: "blacklist" },
  ],
  good_signs: [{ text: "Old domain.", points: -20, area: "domain" }],
  partial: false,
  tranco_list: null,
} as unknown as Analysis;

const FOUND: Comparison = {
  url: "https://bad.example/login",
  asked_at: "2026-11-03T10:00:00Z",
  virustotal: {
    status: "found",
    fresh: false,
    report: {
      stats: { malicious: 5, suspicious: 1, harmless: 50, undetected: 37, timeout: 0 },
      engines: 93,
      flagged: [{ engine: "ESET", category: "malicious", label: "phishing" }],
      categories: [],
      reputation: -36,
      votes: { malicious: 1, harmless: 0 },
      first_seen: "2026-11-01T00:00:00Z",
      last_analysis: "2026-11-02T00:00:00Z",
    },
  },
  phishtank: { status: "listed", phish_id: 77, verified: false, note: "Reported, but never verified by its members." },
};

function render(comparison: Comparison | null, available = true): string {
  const state = comparison ? ({ kind: "done", comparison } as const) : ({ kind: "idle" } as const);
  return renderToStaticMarkup(<CompareReport analysis={ANALYSIS} state={state} run={() => {}} available={available} />);
}

describe("CompareReport", () => {
  it("shows every service's answer beside LinkLens's", () => {
    const html = render(FOUND);
    expect(html).toContain("5 / 93");
    expect(html).toContain("ESET");
    expect(html).toContain("−36");
    expect(html).toContain("Reported, as #77");
    expect(html).toContain("10 of it from LinkLens&#x27;s own checks");
    expect(html).toContain("hxxps://bad[.]example/login");
    expect(html).toContain("Ask VirusTotal for a fresh analysis");
  });

  it("says plainly when a service had nothing, and never shows OpenPhish data", () => {
    const html = render({
      ...FOUND,
      virustotal: { status: "unknown", note: "VirusTotal has never analysed this link." },
      phishtank: { status: "not_listed", note: "No record of this link. Nobody has reported it." },
    });
    expect(html).toContain("VirusTotal has never analysed this link.");
    expect(html).toContain("No record of this link");
    expect(html).toContain("Its terms forbid showing its data");
  });

  it("asks before sending anything, and explains when it can't", () => {
    expect(render(null)).toContain("Compare now");
    expect(render(null, false)).toContain("Comparing needs the scanner to be online");
  });
});

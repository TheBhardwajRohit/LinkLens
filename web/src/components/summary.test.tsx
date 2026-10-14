// The short version of the report, the new report layout, and the trends timeline.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { Analysis, Recon, Scan, Verdict, Visit } from "../lib/api";
import { Advice, KeyFacts, warningText } from "./ReportSummary";
import ScanResults from "./ScanResults";
import { fillDays } from "./Trends";
import { VerdictCard } from "./Verdict";

function scanWith(verdict: Verdict, extra: Partial<Analysis> = {}): Scan {
  const visit: Visit = {
    requested_url: "https://fake-bank.example/login?email=me@example.com",
    final_url: "https://fake-bank.example/login",
    title: "Login",
    status: 200,
    hops: [
      { url: "https://short.example/x", kind: "start", status: 301, blocked: false, reason: null },
      { url: "https://fake-bank.example/login", kind: "server", status: 200, blocked: false, reason: null },
    ],
    blocked: [],
    contacted_domains: [],
    screenshot_jpeg_b64: null,
    html_truncated: false,
    bot_check: null,
    downloads: [],
    popups: [],
    pending_refresh: null,
    stopped: null,
    notes: [],
    duration_ms: 1,
  };
  const recon = {
    host: "fake-bank.example",
    registered_domain: "fake-bank.example",
    registration: { domain: "fake-bank.example", status: "ok", age_days: 3, nameservers: [], flags: [] },
    chain_domains: [],
    dns: null,
    server: { ip: "203.0.113.5", status: "ok", country: "Netherlands", as_org: "Example Hosting" },
    certificate: { trusted: true },
    cert_history: null,
    http: null,
    duration_ms: 0,
  } as unknown as Recon;
  const analysis: Analysis = {
    score: verdict === "dangerous" ? 85 : verdict === "suspicious" ? 50 : 5,
    verdict,
    summary: "This looks like a fake bank login page.",
    scam_type: verdict === "safe" ? null : { id: "banking", label: "Banking fraud", brand: "SBI", evidence: [] },
    reasons: [
      { text: "The page asks for a one-time password (OTP).", points: 30, area: "page" },
      { text: "The domain is only 3 days old.", points: 25, area: "domain" },
      { text: "It shows SBI's name but isn't SBI's real website.", points: 25, area: "page" },
      { text: "The name has several hyphens, like many scam domains.", points: 5, area: "link" },
    ],
    good_signs: [],
    partial: false,
    listed_by: [],
    tranco_list: null,
    ...extra,
  };
  return { id: "abc", url: visit.requested_url, created_at: "2026-10-14T10:00:00Z", visit, recon, analysis, saved: false } as unknown as Scan;
}

describe("Verdict card", () => {
  it("shows the score as a dial and the three main reasons", () => {
    const html = renderToStaticMarkup(<VerdictCard analysis={scanWith("dangerous").analysis} />);
    expect(html).toContain('aria-label="Risk score 85 out of 100"');
    expect(html).toContain("Main reasons");
    expect(html).toContain("one-time password");
    expect(html).not.toContain("several hyphens"); // the fourth reason waits in the full list
    expect(html).toContain("1 more sign under");
  });
});

describe("What should you do?", () => {
  it("gives plain advice, and where to report a scam in India unless the link looks safe", () => {
    const bad = renderToStaticMarkup(<Advice verdict="dangerous" />);
    expect(bad).toContain("Don&#x27;t open this link");
    expect(bad).toContain("cybercrime.gov.in");
    expect(bad).toContain("1930");
    expect(renderToStaticMarkup(<Advice verdict="safe" />)).not.toContain("1930");
  });
});

describe("At a glance", () => {
  it("picks out the domain age, server, certificate, and redirects", () => {
    const html = renderToStaticMarkup(<KeyFacts scan={scanWith("dangerous")} />);
    expect(html).toContain("Only 3 days old");
    expect(html).toContain("Netherlands, hosted by Example Hosting");
    expect(html).toContain("Trusted by browsers");
    expect(html).toContain("1 jump before the final page");
  });

  it("doesn't call the hosting service's age the site's age", () => {
    const scan = scanWith("suspicious", { final_link: { free_hosting: "github.io" } });
    const html = renderToStaticMarkup(<KeyFacts scan={scan} />);
    expect(html).toContain("free hosting service (github.io)");
    expect(html).not.toContain("days old");
  });
});

describe("Warn your family", () => {
  it("writes a short warning with the link broken and without its query string", () => {
    const text = warningText(scanWith("dangerous"), null);
    expect(text).toContain("likely dangerous (85/100)");
    expect(text).toContain("hxxps://fake-bank[.]example/login");
    expect(text).not.toContain("me@example.com");
    expect(text).toContain("Banking fraud (SBI)");
    expect(text).not.toContain("—");
  });
});

describe("Scan report layout", () => {
  it("keeps every section in the page, so printing shows the whole report", () => {
    const html = renderToStaticMarkup(<ScanResults scan={scanWith("dangerous")} reopened={false} sectionRef={null} onScanAnother={() => {}} />);
    for (const part of ["What should you do?", "At a glance", "Warn your family", "Why we flagged it", "Who&#x27;s behind it", "Link trail"]) {
      expect(html).toContain(part);
    }
    expect(html).toContain('role="tablist"');
    expect(html).toContain("hidden print:block");
  });

  it("offers no family warning for a link that looks safe", () => {
    const html = renderToStaticMarkup(<ScanResults scan={scanWith("safe")} reopened={false} sectionRef={null} onScanAnother={() => {}} />);
    expect(html).not.toContain("Warn your family");
  });
});

describe("Trends timeline", () => {
  it("fills in the empty days, oldest first", () => {
    const days = fillDays([{ date: "2026-10-12", safe: 2, suspicious: 1, dangerous: 0 }], 5, new Date("2026-10-14T08:00:00Z"));
    expect(days.map((d) => d.date)).toEqual(["2026-10-10", "2026-10-11", "2026-10-12", "2026-10-13", "2026-10-14"]);
    expect(days[2].safe).toBe(2);
    expect(days[0].safe + days[0].suspicious + days[0].dangerous).toBe(0);
  });
});

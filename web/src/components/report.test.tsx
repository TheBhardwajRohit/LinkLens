// The report must survive old or incomplete saved scans: one bad part says so, the rest still shows.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { Blacklists, Recon } from "../lib/api";
import BlacklistReport from "./BlacklistReport";
import ReconReport from "./ReconReport";

const EMPTY_RECON = {
  host: "example.com",
  registered_domain: "example.com",
  registration: null,
  chain_domains: [],
  dns: null,
  server: null,
  certificate: null,
  cert_history: null,
  http: null,
  duration_ms: 0,
} as Recon;

describe("ReconReport", () => {
  it("draws a certificate that only says whether it's trusted", () => {
    const recon = { ...EMPTY_RECON, certificate: { trusted: true } } as unknown as Recon;
    const html = renderToStaticMarkup(<ReconReport recon={recon} finalUrl="https://example.com/" />);
    expect(html).toContain("Browsers trust it");
  });

  it("draws a registration with missing lists", () => {
    const recon = { ...EMPTY_RECON, registration: { domain: "example.com", status: "ok", age_days: 2 } } as unknown as Recon;
    const html = renderToStaticMarkup(<ReconReport recon={recon} finalUrl="https://example.com/" />);
    expect(html).toContain("example[.]com");
    expect(html).toContain("Registered only 2 days ago");
  });
});

describe("BlacklistReport", () => {
  const base = { threats: [], matched: [], cached: false };
  const blacklists: Blacklists = {
    listed_by: ["Google Safe Browsing"],
    checked: ["https://example.com/"],
    duration_ms: 5,
    sources: [
      { ...base, id: "safe_browsing", name: "Google Safe Browsing", status: "listed", note: "Google lists this link as suspected phishing.", reference: "https://developers.google.com/safe-browsing/v4/advisory" },
      { ...base, id: "virustotal", name: "VirusTotal", status: "not_configured", note: "No VirusTotal key is set, so this check was skipped.", reference: null },
      { ...base, id: "urlhaus", name: "URLhaus (abuse.ch)", status: "clean", note: "Not in URLhaus's list of malware links.", reference: "https://evil.example/not-a-known-service" },
    ],
  };

  it("shows every source with a plain status, and Google's attribution and notice", () => {
    const html = renderToStaticMarkup(<BlacklistReport blacklists={blacklists} />);
    expect(html).toContain("Listed");
    expect(html).toContain("Not set up");
    expect(html).toContain("Advisory provided by Google");
    expect(html).toContain("Google cannot guarantee");
  });

  it("only links out to known services", () => {
    const html = renderToStaticMarkup(<BlacklistReport blacklists={blacklists} />);
    expect(html).not.toContain("evil.example");
  });

  it("draws nothing for scans saved before blacklist checks existed", () => {
    expect(renderToStaticMarkup(<BlacklistReport blacklists={undefined} />)).toBe("");
  });
});

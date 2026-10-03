// The report must survive old or incomplete saved scans: one bad part says so, the rest still shows.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { Blacklists, FamilyResult, GraphResult, Recon, Siblings } from "../lib/api";
import BlacklistReport from "./BlacklistReport";
import BulkScan from "./BulkScan";
import { FamilyCard, SiblingTabs } from "./FamilyReport";
import NetworkMap from "./NetworkMap";
import ReconReport from "./ReconReport";
import ReportActions from "./ReportActions";
import Trends from "./Trends";

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

  it("says whose record it is when the site sits on a free hosting service", () => {
    const recon = { ...EMPTY_RECON, registration: { domain: "github.io", status: "ok", age_days: 4956 } } as unknown as Recon;
    const html = renderToStaticMarkup(<ReconReport recon={recon} finalUrl="https://someone.github.io/" sharedHost="github.io" />);
    expect(html).toContain("free hosting service (github.io)");
    expect(html).toContain("belongs to that service");
    const own = renderToStaticMarkup(<ReconReport recon={recon} finalUrl="https://github.io/" />);
    expect(own).not.toContain("free hosting service");
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

describe("FamilyCard and SiblingTabs", () => {
  const family: FamilyResult = {
    status: "matched",
    note: "Looks 96% like the family.",
    family: { id: 12, label: "fake SBI banking page", brand: "SBI", scam_type: "banking", size: 43, sites: 30, first_seen: "2026-09-03T00:00:00+00:00", last_seen: "2026-09-20T00:00:00+00:00", sample_page: null, percent: 96 },
    similar: [],
    scam_matches: 4,
    copied_site: null,
    library_size: 56000,
  };
  const empty = { status: "none" as const, note: null, items: [], total: 0 };
  const siblings: Siblings = {
    same_server: { status: "ok", note: null, total: 1, items: [{ name: "evil-twin.example.net", why: "same IP address", known_scam: true, source: "library" }] },
    same_owner: empty,
    same_design: empty,
    lookalikes: { ...empty, note: "None of 80 similar names exist." },
  };

  it("names the family like the plan says", () => {
    const html = renderToStaticMarkup(<FamilyCard family={family} />);
    expect(html).toContain("Family #12: fake SBI banking page");
    expect(html).toContain("43 known pages on 30 sites");
    expect(html).toContain("first seen 3 Sept 2026");
    expect(html).toContain("96%");
  });

  it("says so plainly when nothing matches", () => {
    const none = { ...family, status: "none" as const, family: null, note: "Nothing among 500 known pages looks like this one." };
    expect(renderToStaticMarkup(<FamilyCard family={none} />)).toContain("Nothing among 500 known pages");
    expect(renderToStaticMarkup(<FamilyCard family={undefined} />)).toBe("");
  });

  it("shows sibling names defanged, never as links", () => {
    const html = renderToStaticMarkup(<SiblingTabs siblings={siblings} family={family} />);
    expect(html).toContain("evil-twin[.]example[.]net");
    expect(html).not.toContain("<a ");
    expect(html).toContain("known scam");
    expect(html).toContain("Lookalike names");
  });
});

describe("NetworkMap", () => {
  const graph: GraphResult = {
    status: "labelled",
    label: "malicious",
    note: "2 of 3 known sites that link here are scam sites.",
    positive_in: 1,
    negative_in: 2,
    unknown_in: 0,
    links_out: 1,
    scam_links_out: 1,
    triads: 1,
    inferred_edges: 1,
    nodes: [
      { id: "new-site.example.com", label: 0, role: "scanned", why: null },
      { id: "scam-a.example.net", label: -1, role: "both", why: "known scam pages" },
    ],
    edges: [{ source: "scam-a.example.net", target: "new-site.example.com", sign: -1, inferred: false }],
  };

  it("says what the link graph found, in words, and lists the sites defanged", () => {
    const html = renderToStaticMarkup(<NetworkMap graph={graph} />);
    expect(html).toContain("2 of 3 known sites that link here are scam sites.");
    expect(html).toContain("scam-a[.]example[.]net");
    expect(html).toContain("known scam site");
    expect(html).toContain("SiNMULI");
    expect(html).not.toContain('href="http');
  });

  it("draws no map when there are no links, only the note", () => {
    const empty = { ...graph, status: "no_links" as const, label: null, note: "No known site links to this one.", nodes: [graph.nodes[0]], edges: [] };
    const html = renderToStaticMarkup(<NetworkMap graph={empty} />);
    expect(html).toContain("No known site links to this one.");
    expect(html).not.toContain("The same map as a list");
    expect(renderToStaticMarkup(<NetworkMap graph={undefined} />)).toBe("");
  });
});

describe("ReportActions, BulkScan, and Trends", () => {
  it("offers the PDF download, the mistake report, and another scan", () => {
    const html = renderToStaticMarkup(<ReportActions id="abc" saved onScanAnother={() => {}} />);
    expect(html).toContain("Download report (PDF)");
    expect(html).toContain("Report a mistake");
    expect(html).toContain("Copy link to this result");
    expect(html).toContain("print:hidden");
    // An unsaved scan has no link to copy.
    expect(renderToStaticMarkup(<ReportActions id="abc" saved={false} onScanAnother={() => {}} />)).not.toContain("Copy link");
  });

  it("stays out of the way when no scanner is online", () => {
    expect(renderToStaticMarkup(<BulkScan online={false} onOpen={() => {}} />)).toBe("");
    expect(renderToStaticMarkup(<Trends online={false} />)).toBe("");
    expect(renderToStaticMarkup(<BulkScan online onOpen={() => {}} />)).toContain("Scan several links at once");
  });
});

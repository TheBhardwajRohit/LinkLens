import { describe, expect, it } from "vitest";

import type { Visit } from "../lib/api";
import { EXAMPLE_MODEL, modelFromVisit, shortHost } from "./model";
import { createSim, settle } from "./sim";

function visit(overrides: Partial<Visit>): Visit {
  return {
    requested_url: "http://a.example/",
    final_url: "https://c.example/",
    title: null,
    status: 200,
    hops: [],
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
    duration_ms: 1000,
    ...overrides,
  };
}

const hop = (url: string, kind: "start" | "server" | "script" = "server", blocked = false) => ({
  url,
  kind,
  status: blocked ? null : 200,
  blocked,
  reason: blocked ? "private network address" : null,
});

describe("modelFromVisit", () => {
  it("builds the redirect chain from distinct hosts, in order", () => {
    const m = modelFromVisit(
      visit({
        hops: [hop("http://a.example/", "start"), hop("https://a.example/"), hop("https://b.example/x"), hop("https://c.example/")],
      }),
      "k",
    );
    expect(m.chain).toEqual(["a.example", "b.example", "c.example"]);
    expect(m.nodes.map((n) => n.kind)).toEqual(["origin", "hop", "final"]);
    expect(m.links.filter((l) => l.kind === "hop")).toHaveLength(2);
    expect(m.bubbles.map((b) => b.text)).toContain("3 redirects");
  });

  it("links contacted domains and blocked hosts to the final page", () => {
    const m = modelFromVisit(
      visit({
        hops: [hop("https://c.example/", "start")],
        contacted_domains: ["c.example", "cdn.example", "fonts.example"],
        blocked: [{ host: "10.0.0.1", port: 80, reason: "private network address" }],
      }),
      "k",
    );
    expect(m.nodes.find((n) => n.id === "cdn.example")?.kind).toBe("domain");
    expect(m.nodes.find((n) => n.id === "blocked:10.0.0.1")?.kind).toBe("blocked");
    expect(m.nodes.filter((n) => n.id === "c.example")).toHaveLength(1);
    expect(m.bubbles.some((b) => b.tone === "red")).toBe(true);
  });

  it("marks a chain that ends at a blocked address", () => {
    const m = modelFromVisit(
      visit({ stopped: "blocked", hops: [hop("https://a.example/", "start"), hop("http://10.0.0.1/", "server", true)] }),
      "k",
    );
    expect(m.nodes[m.nodes.length - 1].kind).toBe("blocked");
    expect(m.bubbles[m.bubbles.length - 1]).toMatchObject({ tone: "red", text: "Stopped: private network address" });
  });

  it("never shows more than four bubbles", () => {
    const m = modelFromVisit(
      visit({
        hops: [hop("https://a.example/", "start"), hop("https://b.example/"), hop("https://c.example/")],
        contacted_domains: ["d.example"],
        blocked: [{ host: "10.0.0.1", port: 80, reason: "private network address" }],
      }),
      "k",
    );
    expect(m.bubbles.length).toBeLessThanOrEqual(4);
  });
});

describe("shortHost", () => {
  it("defangs and shortens", () => {
    expect(shortHost("login.example.com")).toBe("login[.]example[.]com");
    expect(shortHost("a".repeat(60) + ".com").endsWith("...")).toBe(true);
  });
});

describe("layout", () => {
  it("settles to finite positions with nodes spread apart", () => {
    const sim = settle(createSim(EXAMPLE_MODEL));
    expect(sim.pos.every((p) => p.every(Number.isFinite))).toBe(true);
    const [a, b] = [sim.pos[0], sim.pos[3]];
    expect(Math.hypot(a[0] - b[0], a[1] - b[1])).toBeGreaterThan(1);
  });

  it("is the same every time for the same scan", () => {
    const one = settle(createSim(EXAMPLE_MODEL)).pos;
    const two = settle(createSim(EXAMPLE_MODEL)).pos;
    expect(one).toEqual(two);
  });

  it("keeps the flat (2D) version on one plane", () => {
    const sim = settle(createSim(EXAMPLE_MODEL, true), true);
    expect(sim.pos.every((p) => p[2] === 0)).toBe(true);
  });
});

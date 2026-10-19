// The homepage: its examples must add up and stay harmless, and the page must say what it shows.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import example from "../example/report.json";
import { MESSAGES, SHOWCASE, total } from "./examples";
import Home from "./Home";

describe("Homepage examples", () => {
  it("have reasons that add up to the score shown", () => {
    for (const m of MESSAGES) expect(total(m.reasons)).toBe(m.score);
    for (const s of Object.values(SHOWCASE)) expect(total(s.reasons)).toBe(s.score);
  });

  it("only use reserved .example links, shown defanged", () => {
    for (const link of [...MESSAGES.map((m) => m.link), ...Object.values(SHOWCASE).map((s) => s.link)]) {
      expect(link.startsWith("hxxp")).toBe(true);
      expect(link).toContain("[.]example");
    }
  });
});

describe("Homepage", () => {
  const html = renderToStaticMarkup(<Home />);

  it("leads with the headline and one way into the scanner", () => {
    expect(html).toContain("Don&#x27;t click it.");
    expect(html).toContain('href="/scan/"');
  });

  it("labels every example as an example and never links to one", () => {
    expect(html).toContain("Example message");
    expect(html).toContain("Example report");
    expect(html).not.toMatch(/href="[^"]*\.example/);
  });

  it("keeps the GeoLite credit", () => {
    expect(html).toContain("GeoLite Data created by MaxMind");
  });
});

describe("Saved example report", () => {
  it("is Google's harmless test address and can't be shared or reported", () => {
    expect(example.url).toContain("malware.testing.google.test");
    expect(example.saved).toBe(false);
  });
});

// The scanner page's sections: they must work without a scanner (the live site has none yet) and
// say where their numbers come from.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { EXAMPLE_MODEL } from "../graph/model";
import BrandFigure from "./BrandFigure";
import Knows from "./Knows";
import snapshot from "./library-snapshot.json";
import { sourceLine, type Library } from "./library";
import AnotherLink from "./AnotherLink";
import ScanHero from "./ScanHero";
import YourLink from "./YourLink";
import type { Stats, Trends } from "../lib/api";

const offline: Library = {
  stats: snapshot.stats as unknown as Stats,
  trends: snapshot.trends as unknown as Trends,
  live: false,
  asOf: new Date(`${snapshot.taken}T12:00:00Z`),
};

describe("Scanner page", () => {
  it("leads with the headline and the shared header", () => {
    const html = renderToStaticMarkup(<ScanHero model={EXAMPLE_MODEL}>box</ScanHero>);
    expect(html).toContain("Paste it here.");
    expect(html).toContain('aria-current="page"');
    expect(html).toContain("box");
  });

  it("says plainly what happens to a pasted link", () => {
    const html = renderToStaticMarkup(<YourLink />);
    for (const part of ["First, it&#x27;s cleaned.", "REDACTED", "the site name only", "Not downloaded", "deleted after 90 days"]) {
      expect(html).toContain(part);
    }
    expect(html).not.toMatch(/href="[^"]*\.example/);
  });

  it("shows real library numbers without a scanner, labelled as a snapshot", () => {
    expect(sourceLine(offline)).toContain("snapshot");
    const brand = renderToStaticMarkup(<BrandFigure library={offline} />);
    expect(brand).toContain(offline.trends.brands[0].brand);
    const knows = renderToStaticMarkup(<Knows library={offline} onCheck={() => {}} />);
    expect(knows).toContain("What LinkLens knows");
    expect(knows).toContain("pages fingerprinted");
    expect(knows).toContain("snapshot of the library");
  });

  it("closes with a scan box set in a sentence", () => {
    const html = renderToStaticMarkup(<AnotherLink onCheck={() => {}} />);
    expect(html).toContain("Got another link?");
    expect(html).toContain('type="submit"');
  });
});

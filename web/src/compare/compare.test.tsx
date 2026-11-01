// The comparison page: every number it shows must come from the saved run, nothing from OpenPhish
// may appear, and the links must stay harmless and defanged.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import CompareHero from "./CompareHero";
import EveryLink from "./EveryLink";
import Glance from "./Glance";
import ListsSection from "./ListsSection";
import Method from "./Method";
import VirusTotalDiffs from "./VirusTotalDiffs";
import { byName, ledger, minus, phishTankAnswer, RUN, sum, TESTED, vtAnswer, vtReport } from "./data";

describe("the saved comparison run", () => {
  it("names every tested link, and only tested links", () => {
    expect(TESTED).toHaveLength(RUN.links.length);
    for (const t of TESTED) {
      expect(t.linklens.verdict).toMatch(/safe|suspicious|dangerous/);
      expect(t.phishtank.status).toBeTruthy();
    }
  });

  it("shows each LinkLens score as lines that add up to it, or says what raised it", () => {
    for (const t of TESTED) {
      const { lines, raised } = ledger(t.linklens);
      const added = Math.max(0, Math.min(100, sum(lines)));
      if (raised) expect(t.linklens.score, t.name).toBeGreaterThan(added);
      else expect(added, t.name).toBe(t.linklens.score);
    }
  });

  it("holds nothing from OpenPhish, whose terms forbid sharing its data", () => {
    expect(JSON.stringify(RUN)).not.toMatch(/openphish/i);
  });

  it("uses only harmless links: test pages, real sites, and reserved names", () => {
    const hosts = TESTED.map((t) => new URL(t.url).hostname);
    for (const host of hosts) {
      expect(host).toMatch(/example\.com$|\.example$|onlinesbi\.sbi$|xn--80ak6aa92e\.com$|localtest\.me$|testsafebrowsing\.appspot\.com$|google\.test$|eicar\.org$/);
    }
  });
});

describe("the comparison page", () => {
  const pages = [<CompareHero key="h" />, <VirusTotalDiffs key="v" />, <ListsSection key="l" />, <EveryLink key="e" />, <Glance key="g" />, <Method key="m" />];
  const html = pages.map((p) => renderToStaticMarkup(p)).join("\n");

  it("shows each service's answer as the run recorded it", () => {
    const apple = byName("Fake apple.com");
    expect(vtAnswer(apple).count).toBe(`${vtReport(apple).stats!.malicious} / ${vtReport(apple).engines}`);
    expect(html).toContain(vtAnswer(apple).count!);
    expect(html).toContain(phishTankAnswer(apple).line);
    expect(html).toContain(`Community score <span class="font-display text-2xl font-semibold tabular-nums text-cream">${minus(vtReport(byName("example.com")).reputation!)}`);
    const madeUp = byName("Made-up SBI link");
    expect(vtAnswer(madeUp).line).toBe("Refused to analyse it");
    const listed = TESTED.filter((t) => t.phishtank.status === "listed").length;
    expect(html).toContain(`${listed} of our ${TESTED.length} links are in PhishTank`);
  });

  it("never shows a live link: every tested link appears defanged", () => {
    for (const t of TESTED) {
      expect(html).not.toContain(`>${t.url}<`);
    }
    expect(html).toContain("hxxps://www[.]xn--80ak6aa92e[.]com/");
    expect(html).not.toMatch(/<a [^>]*href="https?:\/\/(?!github\.com|cybercrime\.gov\.in|www\.maxmind\.com)/);
  });

  it("says where VirusTotal is stronger", () => {
    expect(html).toContain("Where VirusTotal is stronger.");
    expect(html).toContain("Yes, its main strength");
  });

  it("keeps OpenPhish to a description and a labelled illustration", () => {
    expect(html).toContain("Illustration with made-up links. OpenPhish&#x27;s own data isn&#x27;t shown.");
    expect(html).toContain("Its terms forbid showing its data");
  });

  it("uses no em-dashes", () => {
    expect(html).not.toContain("—");
  });
});

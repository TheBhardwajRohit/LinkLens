// The comparison page: LinkLens beside VirusTotal, PhishTank, and OpenPhish, on the same links.

import CheckCta from "../home/CheckCta";
import SiteFooter from "../site/SiteFooter";
import CompareHero from "./CompareHero";
import EveryLink from "./EveryLink";
import Glance from "./Glance";
import ListsSection from "./ListsSection";
import Method from "./Method";
import VirusTotalDiffs from "./VirusTotalDiffs";

export default function ComparePage() {
  return (
    <>
      <main>
        <CompareHero />
        <VirusTotalDiffs />
        <ListsSection />
        <EveryLink />
        <Glance />
        <Method />
        <CheckCta />
      </main>
      <SiteFooter />
    </>
  );
}

// The homepage: what LinkLens is, shown working, and one way into the scanner.
import Capabilities from "./Capabilities";
import CheckCta from "./CheckCta";
import SiteFooter from "../site/SiteFooter";
import HomeHero from "./HomeHero";
import HowItWorks from "./HowItWorks";
import ProofBoard from "./ProofBoard";
import ScoreShowcase from "./ScoreShowcase";

export default function Home() {
  return (
    <>
      <main>
        <HomeHero />
        <HowItWorks />
        <ScoreShowcase />
        <Capabilities />
        <ProofBoard />
        <CheckCta />
      </main>
      <SiteFooter />
    </>
  );
}

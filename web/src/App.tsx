import { useRef } from "react";

import Background from "./components/Background";
import Features from "./components/Features";
import Footer from "./components/Footer";
import Hero from "./components/Hero";
import ScanForm from "./components/ScanForm";
import { prefersReducedMotion } from "./lib/device";

export default function App() {
  const inputRef = useRef<HTMLInputElement>(null);

  function scrollToScan() {
    const reduce = prefersReducedMotion();
    document.getElementById("scan")?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
    window.setTimeout(() => inputRef.current?.focus({ preventScroll: true }), reduce ? 0 : 700);
  }

  return (
    <>
      <Background />
      <main>
        <Hero onScanClick={scrollToScan} />
        <Features />
        <ScanForm inputRef={inputRef} />
      </main>
      <Footer />
    </>
  );
}

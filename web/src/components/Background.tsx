import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from "react";

import { canRun3D, prefersReducedMotion } from "../lib/device";

// three.js is big, so it loads after the page is already on screen.
const NetworkScene = lazy(() => import("./NetworkScene"));

type Mode = "pending" | "3d" | "static";

// The background is decoration. If it fails to load or crashes, drop to the static
// gradient instead of taking the whole page down with it.
class SceneGuard extends Component<{ onError: () => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch() {
    this.props.onError();
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}

export default function Background() {
  const [mode, setMode] = useState<Mode>("pending");
  const [ready, setReady] = useState(false);
  const [animate, setAnimate] = useState(() => !prefersReducedMotion());

  useEffect(() => {
    setMode(canRun3D() ? "3d" : "static");
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setAnimate(!mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const fallBackToStatic = () => setMode("static");

  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10">
      {/* Static gradient: shown while the 3D scene loads, and on devices that can't run it. */}
      <div className="bg-fallback absolute inset-0" />
      {mode === "3d" && (
        <div className={`absolute inset-0 transition-opacity duration-1000 ${ready ? "opacity-100" : "opacity-0"}`}>
          <SceneGuard onError={fallBackToStatic}>
            <Suspense fallback={null}>
              <NetworkScene animate={animate} onReady={() => setReady(true)} onLowFps={fallBackToStatic} />
            </Suspense>
          </SceneGuard>
        </div>
      )}
      <div className="bg-vignette absolute inset-0" />
    </div>
  );
}

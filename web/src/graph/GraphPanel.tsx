import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from "react";

import { canRun3D, prefersReducedMotion } from "../lib/device";
import Graph2D from "./Graph2D";
import type { GraphModel } from "./model";

const GraphScene = lazy(() => import("./GraphScene"));

type Mode = "pending" | "3d" | "2d";

// If the 3D code fails to load or crashes, show the flat version instead of breaking the page.
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

function describe(model: GraphModel): string {
  if (model.mode === "example") {
    return "Example: a link that redirects twice, ends at a fake bank login page, and loads from several other domains.";
  }
  if (model.mode === "searching") return "The sandbox is opening the link.";
  return `Graph of the scan: ${model.chain.length} ${model.chain.length === 1 ? "site" : "sites"} in the redirect chain and ${
    model.nodes.length - model.chain.length
  } other connected addresses. Details are in the report below.`;
}

export default function GraphPanel({ model }: { model: GraphModel }) {
  const [mode, setMode] = useState<Mode>("pending");
  const [ready, setReady] = useState(false);
  const [animate, setAnimate] = useState(() => !prefersReducedMotion());

  useEffect(() => {
    setMode(canRun3D() ? "3d" : "2d");
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setAnimate(!mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const showFlat = () => setMode("2d");

  return (
    <div className="relative h-full w-full">
      <p className="sr-only">{describe(model)}</p>
      {mode === "2d" && <Graph2D model={model} />}
      {mode === "3d" && (
        <div className={`absolute inset-0 transition-opacity duration-700 ${ready ? "opacity-100" : "opacity-0"}`}>
          <SceneGuard onError={showFlat}>
            <Suspense fallback={null}>
              <GraphScene model={model} animate={animate} onReady={() => setReady(true)} onLowFps={showFlat} />
            </Suspense>
          </SceneGuard>
        </div>
      )}
      {model.mode === "example" && (
        <span className="absolute bottom-3 left-3 rounded-full border border-white/15 bg-ink/60 px-2.5 py-1 text-[11px] font-medium uppercase tracking-wider text-slate-300 backdrop-blur sm:bottom-6 sm:left-6">
          Example scan
        </span>
      )}
    </div>
  );
}

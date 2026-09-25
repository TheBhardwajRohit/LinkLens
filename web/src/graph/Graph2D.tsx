// Flat, still version of the graph, for devices that can't run 3D (or when the 3D code fails).

import { useMemo } from "react";

import { BUBBLE_TONE, visibleBubbles, type GraphModel, type LinkKind, type NodeKind } from "./model";
import { createSim, settle } from "./sim";

const NODE: Record<NodeKind, { color: string; r: number }> = {
  origin: { color: "#eaf2ff", r: 0.42 },
  hop: { color: "#38bdf8", r: 0.34 },
  final: { color: "#3b82f6", r: 0.64 },
  domain: { color: "#6a8ff0", r: 0.22 },
  blocked: { color: "#f43f5e", r: 0.34 },
  server: { color: "#a78bfa", r: 0.4 },
};
const LINK: Record<LinkKind, { color: string; width: number }> = {
  hop: { color: "#60a5fa", width: 0.2 },
  loads: { color: "#4a6fd1", width: 0.07 },
  blocked: { color: "#f43f5e", width: 0.1 },
  hosted: { color: "#a78bfa", width: 0.14 },
};

export default function Graph2D({ model }: { model: GraphModel }) {
  const sim = useMemo(() => settle(createSim(model, true), true), [model]);
  // SVG's y axis points down, so flip it.
  const pts = sim.pos.map(([x, y]) => [x, -y] as const);
  // Extra room at the top for the bubbles above the highest nodes.
  const pad = 1.4;
  const minX = Math.min(...pts.map((p) => p[0])) - pad;
  const minY = Math.min(...pts.map((p) => p[1])) - pad * 2;
  const w = Math.max(...pts.map((p) => p[0])) + pad - minX;
  const h = Math.max(...pts.map((p) => p[1])) + pad - minY;
  const slots = visibleBubbles(model.bubbles);

  return (
    <div className="absolute inset-0 flex items-center justify-center p-4">
      <div className="relative max-h-full w-full" style={{ aspectRatio: `${w} / ${h}` }}>
        <svg viewBox={`${minX} ${minY} ${w} ${h}`} className="absolute inset-0 h-full w-full" aria-hidden="true">
          <defs>
            <radialGradient id="ll-node-shine" cx="35%" cy="30%" r="70%">
              <stop offset="0%" stopColor="#fff" stopOpacity="0.55" />
              <stop offset="60%" stopColor="#fff" stopOpacity="0" />
            </radialGradient>
          </defs>
          {sim.links.map((l, i) => (
            <line
              key={i}
              x1={pts[l.a][0]}
              y1={pts[l.a][1]}
              x2={pts[l.b][0]}
              y2={pts[l.b][1]}
              stroke={LINK[l.kind].color}
              strokeWidth={LINK[l.kind].width}
              strokeLinecap="round"
            />
          ))}
          {pts.map(([x, y], i) => {
            const style = NODE[sim.kinds[i]];
            return (
              <g key={i}>
                <circle cx={x} cy={y} r={style.r} fill={style.color} />
                <circle cx={x} cy={y} r={style.r} fill="url(#ll-node-shine)" />
              </g>
            );
          })}
        </svg>
        {slots.map(({ bubble, index }) => {
          const i = sim.index.get(bubble.node);
          if (i === undefined) return null;
          const left = ((pts[i][0] - minX) / w) * 100;
          const top = ((pts[i][1] - minY) / h) * 100;
          return (
            <div
              key={index}
              className="bubble-anchor"
              style={{ left: `${left}%`, top: `${top}%`, visibility: "visible", ["--lift" as string]: "14px" }}
            >
              <div className="bubble-place">
                <div className={`bubble-card ${BUBBLE_TONE[bubble.tone]}`}>{bubble.text}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

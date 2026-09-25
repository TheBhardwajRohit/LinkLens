// A tiny force layout: nodes push each other apart, links pull like springs, and the redirect
// chain is nudged into a line from the top left toward the middle, so it reads like a path.
// Small enough (under 50 nodes) that the simple all-pairs version is fast.

import type { GraphModel, LinkKind, NodeKind } from "./model";

export type Vec3 = [number, number, number];

export type Sim = {
  pos: Vec3[];
  vel: Vec3[];
  links: { a: number; b: number; rest: number; kind: LinkKind }[];
  kinds: NodeKind[];
  index: Map<string, number>;
  chainTargets: Map<number, Vec3>;
  alpha: number;
};

const REST: Record<LinkKind, number> = { hop: 2.5, loads: 2.0, blocked: 2.2, hosted: 1.8 };
const REPULSE = 1.3;
const SPRING = 0.08;
const CENTER = 0.012;
const CHAIN_PULL = 0.06;
const DAMPING = 0.82;
const COOLING = 0.985;

// Seeded random numbers, so the same scan always gets the same layout.
function seeded(text: string) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967296;
  };
}

export function createSim(model: GraphModel, flat = false): Sim {
  const rand = seeded(model.key);
  const index = new Map(model.nodes.map((n, i) => [n.id, i]));
  const chain = model.chain.filter((id) => index.has(id));

  // The chain runs diagonally; the final page sits a little right of center.
  const chainTargets = new Map<number, Vec3>();
  const steps = Math.max(chain.length - 1, 1);
  chain.forEach((id, i) => {
    const t = chain.length === 1 ? 1 : i / steps;
    chainTargets.set(index.get(id)!, [-1.9 + 2.4 * t, 2.9 - 3.5 * t, 0]);
  });

  const final = chain.length ? index.get(chain[chain.length - 1])! : 0;
  const pos: Vec3[] = model.nodes.map((_, i) => {
    const base = chainTargets.get(i) ?? chainTargets.get(final) ?? [0, 0, 0];
    return [base[0] + (rand() - 0.5) * 0.6, base[1] + (rand() - 0.5) * 0.6, flat ? 0 : (rand() - 0.5) * 0.6];
  });

  return {
    pos,
    vel: model.nodes.map(() => [0, 0, 0]),
    links: model.links
      .filter((l) => index.has(l.source) && index.has(l.target))
      .map((l) => ({
        a: index.get(l.source)!,
        b: index.get(l.target)!,
        rest: REST[l.kind] * (0.85 + rand() * 0.3),
        kind: l.kind,
      })),
    kinds: model.nodes.map((n) => n.kind),
    index,
    chainTargets,
    alpha: 1,
  };
}

export function tick(sim: Sim, flat = false): void {
  const { pos, vel, alpha } = sim;
  if (alpha < 0.002) return;
  const n = pos.length;

  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const dx = pos[j][0] - pos[i][0];
      const dy = pos[j][1] - pos[i][1];
      const dz = flat ? 0 : pos[j][2] - pos[i][2];
      const d2 = Math.max(dx * dx + dy * dy + dz * dz, 0.04);
      const f = (REPULSE * alpha) / d2;
      const d = Math.sqrt(d2);
      const fx = (dx / d) * f;
      const fy = (dy / d) * f;
      const fz = (dz / d) * f;
      vel[i][0] -= fx;
      vel[i][1] -= fy;
      vel[i][2] -= fz;
      vel[j][0] += fx;
      vel[j][1] += fy;
      vel[j][2] += fz;
    }
  }

  for (const { a, b, rest } of sim.links) {
    const dx = pos[b][0] - pos[a][0];
    const dy = pos[b][1] - pos[a][1];
    const dz = flat ? 0 : pos[b][2] - pos[a][2];
    const d = Math.max(Math.sqrt(dx * dx + dy * dy + dz * dz), 0.001);
    const f = ((d - rest) / d) * SPRING * alpha;
    vel[a][0] += dx * f;
    vel[a][1] += dy * f;
    vel[a][2] += dz * f;
    vel[b][0] -= dx * f;
    vel[b][1] -= dy * f;
    vel[b][2] -= dz * f;
  }

  for (let i = 0; i < n; i++) {
    const target = sim.chainTargets.get(i);
    const pull = target ? CHAIN_PULL : CENTER;
    const [tx, ty, tz] = target ?? [0.4, -0.4, 0];
    vel[i][0] += (tx - pos[i][0]) * pull * alpha;
    vel[i][1] += (ty - pos[i][1]) * pull * alpha;
    vel[i][2] += (tz - pos[i][2]) * pull * alpha;
    for (let k = 0; k < 3; k++) {
      vel[i][k] *= DAMPING;
      pos[i][k] += vel[i][k];
    }
    if (flat) pos[i][2] = 0;
  }
  sim.alpha *= COOLING;
}

/** Run the layout to rest right away (for the static and 2D versions). */
export function settle(sim: Sim, flat = false): Sim {
  for (let i = 0; i < 400 && sim.alpha >= 0.002; i++) tick(sim, flat);
  return sim;
}

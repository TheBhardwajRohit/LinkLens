// The 3D graph in the hero. Glossy nodes joined by "rails", with small packets rolling along the
// redirect chain, and speech bubbles that follow their node as the graph turns.
// Loaded lazily: three.js is big, and the page must not wait for it.

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type RefObject } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

import { BUBBLE_TONE, visibleBubbles, type Bubble, type GraphModel, type LinkKind, type NodeKind } from "./model";
import { createSim, settle, tick, type Sim } from "./sim";

const NODE: Record<NodeKind, { color: string; size: number; halo: number }> = {
  origin: { color: "#eaf2ff", size: 0.42, halo: 1.4 },
  hop: { color: "#38bdf8", size: 0.34, halo: 1.1 },
  final: { color: "#3b82f6", size: 0.64, halo: 2 },
  domain: { color: "#6a8ff0", size: 0.22, halo: 0.6 },
  blocked: { color: "#f43f5e", size: 0.34, halo: 1.6 },
  server: { color: "#a78bfa", size: 0.4, halo: 1.3 },
};
const LINK: Record<LinkKind, { color: string; radius: number }> = {
  hop: { color: "#60a5fa", radius: 0.1 },
  loads: { color: "#4a6fd1", radius: 0.035 },
  blocked: { color: "#f43f5e", radius: 0.05 },
  hosted: { color: "#a78bfa", radius: 0.07 },
};
const PACKETS = 3;
const STEP_MS = 1600; // time between story bubbles in the example
const HOLD_STEPS = 3; // how long the full example story stays up before it restarts
const UP = new THREE.Vector3(0, 1, 0);

type Slot = { bubble: Bubble; index: number };

function ease(x: number): number {
  const c = Math.min(Math.max(x, 0), 1);
  return 1 - (1 - c) ** 3;
}

function makeGlowTexture(): THREE.Texture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.25, "rgba(255,255,255,0.35)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

// Soft studio lighting for reflections, so the spheres and rails look glossy.
function Environment() {
  const { gl, scene } = useThree();
  useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    const room = new RoomEnvironment();
    const env = pmrem.fromScene(room, 0.04).texture;
    scene.environment = env;
    scene.environmentIntensity = 0.55;
    return () => {
      scene.environment = null;
      env.dispose();
      pmrem.dispose();
      room.dispose?.();
    };
  }, [gl, scene]);
  return null;
}

function routesFor(model: GraphModel, sim: Sim): number[][] {
  const chain = model.chain.map((id) => sim.index.get(id)).filter((i): i is number => i !== undefined);
  if (chain.length >= 2) return [chain];
  const final = chain[0] ?? 0;
  return sim.links.filter((l) => l.a === final).slice(0, 6).map((l) => [l.a, l.b]);
}

function Graph({
  model,
  animate,
  slotsRef,
  elsRef,
}: {
  model: GraphModel;
  animate: boolean;
  slotsRef: RefObject<Slot[]>;
  elsRef: RefObject<Map<number, HTMLDivElement>>;
}) {
  const sim = useMemo(() => {
    const s = createSim(model);
    return animate ? s : settle(s);
  }, [model, animate]);
  const n = model.nodes.length;
  const m = sim.links.length;
  const routes = useMemo(() => routesFor(model, sim), [model, sim]);
  const glow = useMemo(makeGlowTexture, []);

  const group = useRef<THREE.Group>(null!);
  const nodes = useRef<THREE.InstancedMesh>(null!);
  const links = useRef<THREE.InstancedMesh>(null!);
  const packets = useRef<THREE.InstancedMesh>(null!);
  const halos = useRef<THREE.Points>(null!);
  const born = useRef<number | null>(null);
  const pointer = useRef({ x: 0, y: 0 });
  const t3 = useMemo(
    () => ({
      m: new THREE.Matrix4(),
      q: new THREE.Quaternion(),
      s: new THREE.Vector3(),
      p: new THREE.Vector3(),
      a: new THREE.Vector3(),
      b: new THREE.Vector3(),
      d: new THREE.Vector3(),
      v: new THREE.Vector3(),
      c: new THREE.Vector3(),
    }),
    [],
  );

  const haloGeometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    const colors = new Float32Array(n * 3);
    const c = new THREE.Color();
    model.nodes.forEach((node, i) => {
      c.set(NODE[node.kind].color).multiplyScalar(NODE[node.kind].halo * 0.35);
      colors.set([c.r, c.g, c.b], i * 3);
    });
    g.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    return g;
  }, [model, n]);

  useLayoutEffect(() => {
    const c = new THREE.Color();
    model.nodes.forEach((node, i) => nodes.current.setColorAt(i, c.set(NODE[node.kind].color)));
    if (nodes.current.instanceColor) nodes.current.instanceColor.needsUpdate = true;
    links.current.count = m;
    sim.links.forEach((l, i) => links.current.setColorAt(i, c.set(LINK[l.kind].color)));
    if (links.current.instanceColor) links.current.instanceColor.needsUpdate = true;
  }, [model, sim, m]);

  useEffect(() => {
    if (!animate) return;
    const onMove = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      pointer.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      pointer.current.y = (e.clientY / window.innerHeight) * 2 - 1;
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, [animate]);

  useFrame(({ clock, camera, size }) => {
    const cam = camera as THREE.PerspectiveCamera;
    const t = clock.elapsedTime;
    if (born.current === null) born.current = t;
    const age = animate ? t - born.current : 99;
    if (animate) tick(sim);
    const { pos } = sim;
    const g = group.current;

    if (animate) {
      g.rotation.y += (Math.sin(t * 0.18) * 0.4 + pointer.current.x * 0.3 - g.rotation.y) * 0.05;
      g.rotation.x += (pointer.current.y * 0.15 - g.rotation.x) * 0.05;
    }

    // Nodes grow in one after another, and the halo follows each node.
    const haloPos = haloGeometry.getAttribute("position") as THREE.BufferAttribute;
    for (let i = 0; i < n; i++) {
      let s = NODE[sim.kinds[i]].size * ease((age - i * 0.035) / 0.6);
      if (model.mode === "searching" && i === 0) s *= 1 + 0.12 * Math.sin(t * 4);
      t3.p.set(pos[i][0], pos[i][1], pos[i][2]);
      t3.s.setScalar(Math.max(s, 1e-4));
      t3.m.compose(t3.p, t3.q.identity(), t3.s);
      nodes.current.setMatrixAt(i, t3.m);
      haloPos.setXYZ(i, pos[i][0], pos[i][1], pos[i][2]);
    }
    nodes.current.instanceMatrix.needsUpdate = true;
    haloPos.needsUpdate = true;

    // Links draw themselves from their source toward their target.
    sim.links.forEach((l, i) => {
      t3.a.set(pos[l.a][0], pos[l.a][1], pos[l.a][2]);
      t3.b.set(pos[l.b][0], pos[l.b][1], pos[l.b][2]);
      t3.d.subVectors(t3.b, t3.a);
      const len = t3.d.length();
      const grow = ease((age - 0.25 - i * 0.02) / 0.6);
      if (len > 1e-6) t3.q.setFromUnitVectors(UP, t3.d.multiplyScalar(1 / len));
      t3.p.copy(t3.a).addScaledVector(t3.d, (len * grow) / 2);
      const r = Math.max(LINK[l.kind].radius * grow, 1e-4);
      t3.s.set(r, Math.max(len * grow, 1e-4), r);
      t3.m.compose(t3.p, t3.q, t3.s);
      links.current.setMatrixAt(i, t3.m);
    });
    links.current.instanceMatrix.needsUpdate = true;

    // Packets roll along the redirect chain (or out to the loaded domains), like marbles on rails.
    for (let k = 0; k < PACKETS; k++) {
      let visible = animate && age > 1.2;
      if (model.mode === "searching") {
        const angle = t * 2 + (k * Math.PI * 2) / PACKETS;
        t3.p.set(pos[0][0] + Math.cos(angle) * 0.75, pos[0][1] + Math.sin(angle) * 0.75, Math.sin(t + k) * 0.3);
      } else if (routes.length) {
        const phase = t * 0.28 + k / PACKETS;
        const route = routes[(Math.floor(phase) + k) % routes.length];
        const u = (phase % 1) * (route.length - 1);
        const seg = Math.min(Math.floor(u), route.length - 2);
        const f = u - seg;
        const [from, to] = [pos[route[seg]], pos[route[seg + 1]]];
        t3.p.set(from[0] + (to[0] - from[0]) * f, from[1] + (to[1] - from[1]) * f, from[2] + (to[2] - from[2]) * f);
      } else {
        visible = false;
      }
      t3.s.setScalar(visible ? 0.11 : 1e-4);
      t3.m.compose(t3.p, t3.q.identity(), t3.s);
      packets.current.setMatrixAt(k, t3.m);
    }
    packets.current.instanceMatrix.needsUpdate = true;

    // Keep the whole graph in view, with room for the bubbles.
    t3.c.set(0, 0, 0);
    for (const p of pos) t3.c.add(t3.v.set(p[0], p[1], p[2]));
    t3.c.multiplyScalar(1 / n);
    // Never zoom in closer than this, so a one-node graph doesn't fill the whole panel.
    let radius = 1.8;
    for (const p of pos) radius = Math.max(radius, t3.v.set(p[0], p[1], p[2]).distanceTo(t3.c));
    radius += 0.55;
    const vfov = THREE.MathUtils.degToRad(cam.fov);
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * cam.aspect);
    const dist = (radius / Math.sin(Math.min(vfov, hfov) / 2)) * 0.92;
    g.updateMatrixWorld();
    g.localToWorld(t3.c);
    const follow = animate ? 0.06 : 1;
    cam.position.lerp(t3.v.set(t3.c.x, t3.c.y, t3.c.z + dist), follow);
    cam.lookAt(t3.c);
    cam.updateMatrixWorld();

    // Pin each bubble above its node. Flip it below if it would hit the top or another bubble.
    const placed: { x: number; y: number; below: boolean }[] = [];
    for (const slot of slotsRef.current ?? []) {
      const el = elsRef.current?.get(slot.index);
      const i = sim.index.get(slot.bubble.node);
      if (!el || i === undefined) continue;
      t3.v.set(pos[i][0], pos[i][1], pos[i][2]);
      g.localToWorld(t3.v);
      const depth = t3.v.distanceTo(cam.position);
      t3.v.project(cam);
      if (t3.v.z > 1) {
        el.style.visibility = "hidden";
        continue;
      }
      const half = Math.min(115, size.width / 2 - 6);
      const x = Math.min(Math.max(((t3.v.x + 1) / 2) * size.width, half + 4), size.width - half - 4);
      const y = ((1 - t3.v.y) / 2) * size.height;
      const lift = (NODE[sim.kinds[i]].size * size.height) / (2 * Math.tan(vfov / 2) * depth);
      const below =
        y < 90 || placed.some((p) => !p.below && Math.abs(p.x - x) < 170 && Math.abs(p.y - y) < 60);
      el.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      el.style.setProperty("--lift", `${lift + 8}px`);
      el.dataset.below = String(below);
      el.style.visibility = "visible";
      placed.push({ x, y, below });
    }
  });

  return (
    <group ref={group}>
      <instancedMesh ref={links} args={[undefined, undefined, Math.max(m, 1)]}>
        <cylinderGeometry args={[1, 1, 1, 12, 1, true]} />
        <meshPhysicalMaterial roughness={0.22} metalness={0.2} clearcoat={1} clearcoatRoughness={0.1} />
      </instancedMesh>
      <instancedMesh ref={nodes} args={[undefined, undefined, n]}>
        <sphereGeometry args={[1, 40, 20]} />
        <meshPhysicalMaterial roughness={0.16} metalness={0.05} clearcoat={1} clearcoatRoughness={0.06} />
      </instancedMesh>
      <instancedMesh ref={packets} args={[undefined, undefined, PACKETS]}>
        <sphereGeometry args={[1, 20, 12]} />
        <meshBasicMaterial color="#e0f2fe" toneMapped={false} />
      </instancedMesh>
      <points ref={halos} geometry={haloGeometry}>
        <pointsMaterial
          map={glow}
          size={2}
          vertexColors
          sizeAttenuation
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
    </group>
  );
}

// If the device can't keep up (under 24 frames a second), switch to the flat version.
function FpsGuard({ onLow }: { onLow: () => void }) {
  const s = useRef({ start: 0, last: 0, frames: 0, done: false });
  useFrame(({ clock }) => {
    const st = s.current;
    const t = clock.elapsedTime;
    if (st.done || t < 1.5) return;
    if (!st.start || t - st.last > 0.5) {
      st.start = t;
      st.frames = 0;
    }
    st.last = t;
    st.frames++;
    if (t - st.start >= 3) {
      st.done = true;
      if (st.frames / (t - st.start) < 24) onLow();
    }
  });
  return null;
}

// How many story bubbles are showing. The example plays as a looping story;
// a real result reveals its bubbles once, a moment after the graph appears.
function useStoryStep(model: GraphModel, animate: boolean): number {
  const total = model.bubbles.length;
  const [step, setStep] = useState(animate ? 0 : total);
  useEffect(() => {
    if (!animate || model.mode === "searching") {
      setStep(total);
      return;
    }
    setStep(0);
    let count = 0;
    const loop = model.mode === "example";
    const every = loop ? STEP_MS : 450;
    let timer = 0;
    const start = window.setTimeout(() => {
      timer = window.setInterval(() => {
        count += 1;
        if (loop && count > total + HOLD_STEPS) count = 0;
        if (!loop && count >= total) window.clearInterval(timer);
        setStep(Math.min(count, total));
      }, every);
    }, 900);
    return () => {
      window.clearTimeout(start);
      window.clearInterval(timer);
    };
  }, [model, animate, total]);
  return step;
}

export default function GraphScene({
  model,
  animate,
  onReady,
  onLowFps,
}: {
  model: GraphModel;
  animate: boolean;
  onReady: () => void;
  onLowFps: () => void;
}) {
  const step = useStoryStep(model, animate);
  const slots = useMemo(() => visibleBubbles(model.bubbles.slice(0, step)), [model, step]);
  const slotsRef = useRef<Slot[]>(slots);
  slotsRef.current = slots;
  const elsRef = useRef(new Map<number, HTMLDivElement>());
  const invalidate = useRef<() => void>(() => {});

  // In still mode the scene only redraws on request, so ask for a frame when bubbles change.
  useEffect(() => invalidate.current(), [slots]);

  return (
    <div className="absolute inset-0">
      <Canvas
        aria-hidden="true"
        frameloop={animate ? "always" : "demand"}
        dpr={[1, 1.75]}
        camera={{ position: [0, 0, 12], fov: 38, near: 0.1, far: 100 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        onCreated={(state) => {
          invalidate.current = state.invalidate;
          onReady();
        }}
      >
        <Environment />
        <ambientLight intensity={0.25} />
        <directionalLight position={[3, 5, 6]} intensity={2} />
        <pointLight position={[-4, -2, 3]} color="#ff5a3c" intensity={22} />
        <pointLight position={[4, 3, -2]} color="#3b82f6" intensity={45} />
        <Graph key={model.key} model={model} animate={animate} slotsRef={slotsRef} elsRef={elsRef} />
        {animate && <FpsGuard onLow={onLowFps} />}
      </Canvas>

      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <AnimatePresence>
          {slots.map(({ bubble, index }) => (
            <div
              key={`${model.key}:${index}`}
              ref={(el) => {
                if (el) elsRef.current.set(index, el);
                else elsRef.current.delete(index);
              }}
              className="bubble-anchor"
            >
              <div className="bubble-place">
                <motion.div
                  className={`bubble-card ${BUBBLE_TONE[bubble.tone]}`}
                  initial={animate ? { opacity: 0, scale: 0.6, y: 8 } : false}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.85, transition: { duration: 0.2 } }}
                  transition={{ type: "spring", stiffness: 380, damping: 24 }}
                >
                  {bubble.text}
                </motion.div>
              </div>
            </div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

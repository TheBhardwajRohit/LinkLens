// The 3D "web of links" behind the homepage: layers of glowing dots joined by thin lines.
// Most dots are blue or cyan. A few are red: scam sites hidden among normal ones.

import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

const BG = "#05070d";
const CAMERA_Z = 10;
const FOV = 60;
const BLUES = ["#22d3ee", "#38bdf8", "#60a5fa", "#67e8f9", "#7dd3fc"].map((c) => new THREE.Color(c));
const RED = new THREE.Color("#f43f5e");
const RED_SHARE = 0.06;

type LayerSpec = { z: number; count: number; size: number; link: number; drift: number; lineOpacity: number };

// Closest layer first. Far layers get bigger dots so they stay visible; the fog still fades them.
const LAYERS: LayerSpec[] = [
  { z: 3, count: 24, size: 0.42, link: 2.8, drift: 0.018, lineOpacity: 0.4 },
  { z: -2, count: 70, size: 0.46, link: 2.7, drift: 0.013, lineOpacity: 0.34 },
  { z: -9, count: 120, size: 0.6, link: 3.3, drift: 0.009, lineOpacity: 0.28 },
  { z: -18, count: 170, size: 0.8, link: 4.3, drift: 0.006, lineOpacity: 0.24 },
];

// Small seeded random generator, so the layout is the same on every visit.
function mulberry32(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type LayerData = { dots: THREE.BufferGeometry; reds: THREE.BufferGeometry; lines: THREE.BufferGeometry };

// Layer counts are tuned for a wide desktop screen. Narrower screens get a narrower field
// with the same number of dots per area, so phones look just as full with less work.
const WIDEST_ASPECT = 2.4;

function buildLayer(spec: LayerSpec, seed: number, aspect: number): LayerData {
  const rand = mulberry32(seed);
  const distance = CAMERA_Z - spec.z;
  const visibleHeight = 2 * distance * Math.tan((FOV * Math.PI) / 360);
  // Extra room so mouse and scroll parallax never reveal an empty edge.
  const height = visibleHeight * 1.25 + 7;
  const fullWidth = visibleHeight * WIDEST_ASPECT + 6;
  const width = visibleHeight * Math.min(Math.max(aspect, 0.5) * 1.15, WIDEST_ASPECT) + 6;
  const n = Math.round((spec.count * width) / fullWidth);

  const points: THREE.Vector3[] = [];
  const colors: THREE.Color[] = [];
  const dotPos: number[] = [];
  const dotCol: number[] = [];
  const redPos: number[] = [];

  for (let i = 0; i < n; i++) {
    const p = new THREE.Vector3((rand() - 0.5) * width, (rand() - 0.5) * height, spec.z + (rand() - 0.5) * 2.5);
    const isRed = rand() < RED_SHARE;
    const color = isRed ? RED : BLUES[Math.floor(rand() * BLUES.length)];
    points.push(p);
    colors.push(color);
    if (isRed) {
      redPos.push(p.x, p.y, p.z);
    } else {
      dotPos.push(p.x, p.y, p.z);
      dotCol.push(color.r, color.g, color.b);
    }
  }

  // Join each dot to a couple of close neighbours, capping links per dot to avoid clutter.
  const degree = new Array<number>(n).fill(0);
  const linePos: number[] = [];
  const lineCol: number[] = [];
  for (let i = 0; i < n; i++) {
    const near: [number, number][] = [];
    for (let j = i + 1; j < n; j++) {
      const d = points[i].distanceTo(points[j]);
      if (d < spec.link) near.push([d, j]);
    }
    near.sort((a, b) => a[0] - b[0]);
    for (const [, j] of near) {
      if (degree[i] >= 3) break;
      if (degree[j] >= 4) continue;
      degree[i]++;
      degree[j]++;
      linePos.push(points[i].x, points[i].y, points[i].z, points[j].x, points[j].y, points[j].z);
      for (const c of [colors[i], colors[j]]) lineCol.push(c.r * 0.7, c.g * 0.7, c.b * 0.7);
    }
  }

  const dots = new THREE.BufferGeometry();
  dots.setAttribute("position", new THREE.Float32BufferAttribute(dotPos, 3));
  dots.setAttribute("color", new THREE.Float32BufferAttribute(dotCol, 3));
  const reds = new THREE.BufferGeometry();
  reds.setAttribute("position", new THREE.Float32BufferAttribute(redPos, 3));
  const lines = new THREE.BufferGeometry();
  lines.setAttribute("position", new THREE.Float32BufferAttribute(linePos, 3));
  lines.setAttribute("color", new THREE.Float32BufferAttribute(lineCol, 3));
  return { dots, reds, lines };
}

function makeGlowTexture(): THREE.Texture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.12, "rgba(255,255,255,1)");
  g.addColorStop(0.3, "rgba(255,255,255,0.45)");
  g.addColorStop(0.6, "rgba(255,255,255,0.1)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function Layer({ spec, data, glow, index, animate }: {
  spec: LayerSpec;
  data: LayerData;
  glow: THREE.Texture;
  index: number;
  animate: boolean;
}) {
  const group = useRef<THREE.Group>(null);
  const redMaterial = useRef<THREE.PointsMaterial>(null);
  const phase = index * 1.7;

  useFrame(({ clock }) => {
    if (!animate || !group.current) return;
    const t = clock.elapsedTime;
    group.current.position.x = Math.sin(t * spec.drift * 5 + phase) * 0.7;
    group.current.position.y = Math.cos(t * spec.drift * 4 + phase) * 0.45;
    group.current.rotation.z = Math.sin(t * spec.drift * 2 + phase) * 0.06;
    if (redMaterial.current) redMaterial.current.opacity = 0.65 + 0.35 * Math.sin(t * 1.6 + phase);
  });

  const common = { transparent: true, depthWrite: false, blending: THREE.AdditiveBlending } as const;
  return (
    <group ref={group}>
      <lineSegments geometry={data.lines}>
        <lineBasicMaterial vertexColors opacity={spec.lineOpacity} {...common} />
      </lineSegments>
      {/* Soft halo drawn under each dot, so the dots read as glowing. */}
      <points geometry={data.dots}>
        <pointsMaterial map={glow} size={spec.size * 3} vertexColors opacity={0.14} sizeAttenuation {...common} />
      </points>
      <points geometry={data.dots}>
        <pointsMaterial map={glow} size={spec.size} vertexColors sizeAttenuation {...common} />
      </points>
      <points geometry={data.reds}>
        <pointsMaterial map={glow} size={spec.size * 4} color={RED} opacity={0.2} sizeAttenuation {...common} />
      </points>
      <points geometry={data.reds}>
        <pointsMaterial ref={redMaterial} map={glow} size={spec.size * 1.4} color={RED} sizeAttenuation {...common} />
      </points>
    </group>
  );
}

// Moves the camera a little with the mouse and with page scroll. Near layers shift more than far ones.
function Rig() {
  const pointer = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      pointer.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      pointer.current.y = (e.clientY / window.innerHeight) * 2 - 1;
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, []);

  useFrame(({ camera }) => {
    const scroll = Math.min(window.scrollY / Math.max(window.innerHeight, 1), 3);
    const tx = pointer.current.x * 1.3;
    const ty = -pointer.current.y * 0.8 - scroll * 0.8;
    camera.position.x += (tx - camera.position.x) * 0.035;
    camera.position.y += (ty - camera.position.y) * 0.035;
    camera.lookAt(0, camera.position.y * 0.6, -12);
  });
  return null;
}

// If the device can't keep up (under 24 frames a second), switch to the static background.
function FpsGuard({ onLow }: { onLow: () => void }) {
  const s = useRef({ start: 0, last: 0, frames: 0, done: false });
  useFrame(({ clock }) => {
    const st = s.current;
    const t = clock.elapsedTime;
    if (st.done || t < 1.5) return;
    if (!st.start || t - st.last > 0.5) {
      // First sample, or the tab was hidden for a while: start measuring again.
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

// Screen width / height, rounded so small resizes don't rebuild the scene.
function useAspect(): number {
  const read = () => Math.round((window.innerWidth / Math.max(window.innerHeight, 1)) * 4) / 4;
  const [aspect, setAspect] = useState(read);
  useEffect(() => {
    const onResize = () => setAspect(read());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return aspect;
}

export default function NetworkScene({ animate, onReady, onLowFps }: {
  animate: boolean;
  onReady: () => void;
  onLowFps: () => void;
}) {
  const small = window.innerWidth < 768;
  const aspect = useAspect();
  const glow = useMemo(makeGlowTexture, []);
  const layers = useMemo(() => LAYERS.map((spec, i) => buildLayer(spec, 1234 + i * 97, aspect)), [aspect]);

  return (
    <Canvas
      frameloop={animate ? "always" : "demand"}
      dpr={small ? [1, 1.25] : [1, 1.5]}
      camera={{ position: [0, 0, CAMERA_Z], fov: FOV, near: 0.1, far: 60 }}
      gl={{ antialias: false, alpha: false, powerPreference: "low-power" }}
      onCreated={onReady}
    >
      <color attach="background" args={[BG]} />
      <fog attach="fog" args={[BG, 9, 36]} />
      {LAYERS.map((spec, i) => (
        <Layer key={i} spec={spec} data={layers[i]} glow={glow} index={i} animate={animate} />
      ))}
      {animate && <Rig />}
      {animate && <FpsGuard onLow={onLowFps} />}
    </Canvas>
  );
}

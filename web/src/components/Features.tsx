import { motion, useReducedMotion, useScroll, useSpring, useTransform, type MotionValue } from "motion/react";
import { useRef, type PointerEvent } from "react";

import { FEATURES, type Feature } from "../features";

// Each card sits at one of three depths. Nearer cards are bigger, brighter, and move more on scroll.
const DEPTHS = [0, 2, 1, 2, 0, 1, 0, 2, 0, 1];
const DEPTH_STYLE = [
  { scale: 1, shift: 22, float: 5, cls: "bg-panel/90 border-cyan-300/25 shadow-[0_30px_80px_-30px_rgba(34,211,238,0.45)]" },
  { scale: 0.96, shift: 12, float: 6.5, cls: "bg-panel/75 border-line shadow-[0_20px_50px_-30px_rgba(34,211,238,0.3)]" },
  { scale: 0.92, shift: 4, float: 8, cls: "bg-panel/60 border-line/70 opacity-90" },
];
const TILT = 14;

function FeatureCard({ feature, depth, index, progress, reduce }: {
  feature: Feature;
  depth: number;
  index: number;
  progress: MotionValue<number>;
  reduce: boolean;
}) {
  const d = DEPTH_STYLE[depth];
  const y = useTransform(progress, [0, 1], [d.shift, -d.shift]);
  const rotateX = useSpring(0, { stiffness: 180, damping: 18 });
  const rotateY = useSpring(0, { stiffness: 180, damping: 18 });
  const Icon = feature.icon;

  function tilt(e: PointerEvent<HTMLElement>) {
    if (reduce || e.pointerType !== "mouse") return;
    const r = e.currentTarget.getBoundingClientRect();
    rotateY.set(((e.clientX - r.left) / r.width - 0.5) * TILT);
    rotateX.set(-((e.clientY - r.top) / r.height - 0.5) * TILT);
  }
  function untilt() {
    rotateX.set(0);
    rotateY.set(0);
  }

  return (
    <motion.div style={reduce ? undefined : { y }} className="relative h-full hover:z-10">
      <motion.div
        className="h-full"
        initial={reduce ? false : { opacity: 0, y: 28 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.6, delay: (index % 5) * 0.07, ease: "easeOut" }}
      >
        <motion.div
          className="h-full"
          animate={reduce ? undefined : { y: [0, -6, 0] }}
          transition={{ duration: d.float, repeat: Infinity, ease: "easeInOut", delay: (index % 5) * 0.45 }}
        >
          <motion.article
            onPointerMove={tilt}
            onPointerLeave={untilt}
            style={{ rotateX, rotateY, scale: d.scale, transformPerspective: 900 }}
            whileHover={reduce ? undefined : { scale: d.scale * 1.04 }}
            className={`h-full rounded-2xl border p-5 lg:p-4 xl:p-5 ${d.cls}`}
          >
            <div
              className={`mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl ring-1 ${
                feature.danger ? "bg-rose-500/10 text-rose-300 ring-rose-400/25" : "bg-cyan-400/10 text-cyan-300 ring-cyan-300/20"
              }`}
            >
              <Icon className="h-5 w-5" aria-hidden="true" />
            </div>
            <h3 className="font-display text-base font-semibold text-slate-100">{feature.title}</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-400">{feature.text}</p>
          </motion.article>
        </motion.div>
      </motion.div>
    </motion.div>
  );
}

export default function Features() {
  const ref = useRef<HTMLElement>(null);
  const reduce = useReducedMotion() ?? false;
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });

  return (
    <section id="features" ref={ref} className="relative mx-auto max-w-7xl scroll-mt-8 px-4 py-24 sm:py-32">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="font-display text-3xl font-semibold tracking-tight text-white sm:text-5xl">What LinkLens tells you</h2>
        <p className="mt-4 text-slate-400">Ten checks from one scan. Nothing to install, and you never open the link yourself.</p>
      </div>
      <div className="mt-16 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
        {FEATURES.map((feature, i) => (
          <FeatureCard
            key={feature.title}
            feature={feature}
            depth={DEPTHS[i]}
            index={i}
            progress={scrollYProgress}
            reduce={reduce}
          />
        ))}
      </div>
    </section>
  );
}

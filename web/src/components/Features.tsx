import { motion, useReducedMotion } from "motion/react";
import type { PointerEvent } from "react";

import { FEATURES, type Feature } from "../features";

function FeatureCard({ feature, index, reduce }: { feature: Feature; index: number; reduce: boolean }) {
  const Icon = feature.icon;
  const live = feature.status === "live";

  // A soft light that follows the mouse across the card.
  function spotlight(e: PointerEvent<HTMLElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
    e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
  }

  return (
    <motion.article
      onPointerMove={spotlight}
      initial={reduce ? false : { opacity: 0, y: 22 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.5, delay: (index % 5) * 0.06, ease: "easeOut" }}
      className="glass-card group relative overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.035] p-5 backdrop-blur-md transition-[translate,border-color,box-shadow,background-color] duration-300 hover:-translate-y-1 hover:border-blue-400/35 hover:bg-white/[0.05] hover:shadow-[0_24px_60px_-24px_rgba(59,130,246,0.6)] motion-reduce:hover:translate-y-0"
    >
      <div aria-hidden="true" className="card-spotlight pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
      <div className="relative flex items-start justify-between gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-300 ring-1 ring-blue-400/20">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ring-1 ${
            live ? "bg-blue-500/15 text-blue-200 ring-blue-400/30" : "bg-white/5 text-slate-400 ring-white/10"
          }`}
        >
          {live ? "Live" : "Coming soon"}
        </span>
      </div>
      <h3 className="relative mt-4 font-display text-base font-semibold text-cream">{feature.title}</h3>
      <p className="relative mt-1.5 text-sm leading-relaxed text-slate-400">{feature.text}</p>
    </motion.article>
  );
}

export default function Features() {
  const reduce = useReducedMotion() ?? false;
  const live = FEATURES.filter((f) => f.status === "live").length;

  return (
    <section id="features" className="mx-auto max-w-[88rem] scroll-mt-8 px-5 py-24 sm:px-8 sm:py-32">
      <div className="max-w-2xl">
        <h2 className="font-display text-3xl font-medium tracking-tight text-cream sm:text-5xl">What LinkLens tells you</h2>
        <p className="mt-4 text-slate-400">
          {live} of these checks work today. The rest arrive as the project grows, and each card switches to Live when
          its check ships.
        </p>
      </div>
      <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {FEATURES.map((feature, i) => (
          <FeatureCard key={feature.title} feature={feature} index={i} reduce={reduce} />
        ))}
      </div>
    </section>
  );
}

// Small pieces the homepage sections share: the score dial, entrances, and the one button shape.

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

import type { Verdict } from "../lib/api";
import { VERDICT_STROKE } from "./examples";

/** The page's one button shape: fully round, flat. */
export const PILL =
  "inline-flex items-center justify-center gap-2 rounded-full px-6 py-3.5 text-[17px] font-semibold transition-[background-color,transform] duration-150 active:scale-[0.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300 motion-reduce:active:scale-100";

/** One part of a section arriving as it scrolls into view: rises a little and fades in, once.
 * Parts of a section pass their place in reading order, so they arrive one after another. */
export function Reveal({
  children,
  order = 0,
  className,
  as = "div",
}: {
  children: ReactNode;
  order?: number;
  className?: string;
  as?: "div" | "li" | "p";
}) {
  const reduce = useReducedMotion() ?? false;
  const Tag = motion[as];
  return (
    <Tag
      className={className}
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "0px 0px -12% 0px" }}
      transition={{ duration: reduce ? 0.2 : 0.7, delay: order * 0.08, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </Tag>
  );
}

/** A half-circle score dial, the same reading as the report's. */
export function Dial({ score, verdict, className = "w-40" }: { score: number; verdict: Verdict; className?: string }) {
  const filled = Math.min(Math.max(score, 0), 100);
  return (
    <div className={`relative shrink-0 ${className}`} role="img" aria-label={`Risk score ${score} out of 100`}>
      <svg viewBox="0 0 120 68" className="w-full" aria-hidden="true">
        <path d="M 10 60 A 50 50 0 0 1 110 60" pathLength={100} fill="none" strokeWidth="10" strokeLinecap="round" className="stroke-white/10" />
        {filled > 0 && (
          <path
            d="M 10 60 A 50 50 0 0 1 110 60"
            pathLength={100}
            fill="none"
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={`${filled} 100`}
            stroke={VERDICT_STROKE[verdict]}
            className="transition-[stroke-dasharray] duration-700"
          />
        )}
      </svg>
      <p className="absolute inset-x-0 bottom-0 text-center font-display text-4xl font-semibold leading-none text-cream tabular-nums">
        {score}
      </p>
    </div>
  );
}

/** "+30" or "-6", for a reason's points. */
export function points(n: number): string {
  return n > 0 ? `+${n}` : `${n}`;
}

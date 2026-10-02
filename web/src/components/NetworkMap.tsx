// "Network map": the scanned site, the sites it links to, and the known sites that link to it.
// Red is a known scam site, green a known honest one, grey unknown. The verdict from the link
// graph (who links here) is said in words above the map.

import { Info, Network } from "lucide-react";
import { lazy, Suspense, useCallback, useMemo, useState } from "react";

import type { GraphResult } from "../lib/api";
import Guard from "./Guard";
import { Section } from "./ReportParts";

const NetworkCanvas = lazy(() => import("./NetworkCanvas"));

const defang = (name: string) => name.replaceAll(".", "[.]");
const LABEL = { "1": "known honest site", "-1": "known scam site", "0": "unknown site" } as const;
const ROLE: Record<string, string> = {
  scanned: "the site you scanned",
  links_to: "this site links to it",
  linked_from: "it links to this site",
  both: "they link to each other",
  neighbour: "linked with a neighbour",
};

function Dot({ color }: { color: string }) {
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} aria-hidden="true" />;
}

export default function NetworkMap({ graph }: { graph: GraphResult | undefined }) {
  const [selected, setSelected] = useState<string | null>(null);
  const onSelect = useCallback((id: string | null) => setSelected(id), []);
  const nodes = useMemo(() => graph?.nodes ?? [], [graph]);
  const edges = useMemo(() => graph?.edges ?? [], [graph]);
  if (!graph || graph.status === "skipped") return null;

  const picked = nodes.find((n) => n.id === selected) ?? null;
  const tone =
    graph.label === "malicious" || graph.scam_links_out > 0
      ? "border-rose-400/30 bg-rose-500/[0.04]"
      : "border-white/[0.08] bg-ink/40";
  const known = graph.positive_in + graph.negative_in;

  return (
    <Section title="Network map">
      <div className={`rounded-xl border p-4 ${tone}`}>
        <p className="flex items-start gap-2 text-sm text-slate-200">
          <Network className="mt-0.5 h-4 w-4 shrink-0 text-blue-400" aria-hidden="true" />
          {graph.note}
        </p>
        <p className="mt-2 text-xs text-slate-500">
          {graph.links_out} {graph.links_out === 1 ? "site" : "sites"} linked from this page, {known} known{" "}
          {known === 1 ? "site links" : "sites link"} to it
          {graph.unknown_in > 0 && `, ${graph.unknown_in} unknown`}
          {graph.inferred_edges > 0 && `. ${graph.inferred_edges} link signs were worked out from their neighbours`}.
        </p>
      </div>

      {edges.length > 0 && (
        <div className="mt-3">
          <Guard name="network map">
            <Suspense fallback={<div className="h-[380px] rounded-xl border border-white/[0.08] bg-ink/60" />}>
              <NetworkCanvas nodes={nodes} edges={edges} onSelect={onSelect} />
            </Suspense>
          </Guard>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
            <span className="inline-flex items-center gap-1.5"><Dot color="bg-rose-500" /> known scam</span>
            <span className="inline-flex items-center gap-1.5"><Dot color="bg-emerald-500" /> known honest</span>
            <span className="inline-flex items-center gap-1.5"><Dot color="bg-slate-500" /> unknown</span>
            <span className="inline-flex items-center gap-1.5"><Dot color="bg-blue-500" /> ring: the scanned site</span>
            <span>Arrows show who links to whom. Drag, scroll to zoom, click a dot.</span>
          </div>
          <p aria-live="polite" className="mt-2 min-h-5 text-sm text-slate-300">
            {picked && (
              <>
                <span className="font-mono text-[13px]">{defang(picked.id)}</span>
                <span className="text-slate-400">
                  : {LABEL[String(picked.label) as keyof typeof LABEL]}
                  {picked.why ? ` (${picked.why})` : ""}, {ROLE[picked.role] ?? picked.role}
                </span>
              </>
            )}
          </p>
          <details className="mt-1 text-sm">
            <summary className="cursor-pointer text-slate-400 hover:text-white">The same map as a list</summary>
            <ul className="mt-2 columns-1 gap-6 sm:columns-2">
              {nodes.slice(1).map((n) => (
                <li key={n.id} className="break-all py-0.5 text-slate-400">
                  <span className="font-mono text-[13px] text-slate-300">{defang(n.id)}</span>: {LABEL[String(n.label) as keyof typeof LABEL]},{" "}
                  {ROLE[n.role] ?? n.role}
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}

      <p className="mt-2 flex items-start gap-1.5 text-xs text-slate-500">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        Built from the pages LinkLens has seen, not the whole web. New domains have few known links, so the graph often
        has nothing to say about them. Method: SiNMULI (Gayen, Mondal, Jana, 2026).
      </p>
    </Section>
  );
}

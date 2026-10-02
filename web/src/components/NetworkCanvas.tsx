// The drawing part of the network map (Cytoscape.js). Loaded only when a report has a graph to
// show, so the library stays out of the first page load. Everything is drawn on a canvas, and
// names are defanged text, so nothing here is a link.

import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { useEffect, useRef } from "react";

import type { GraphEdge, GraphNode } from "../lib/api";
import { prefersReducedMotion } from "../lib/device";

const COLOR = { honest: "#10b981", scam: "#f43f5e", unknown: "#64748b", scanned: "#3b82f6", text: "#cbd5e1" };

const colorOf = (label: number) => (label > 0 ? COLOR.honest : label < 0 ? COLOR.scam : COLOR.unknown);
const defang = (name: string) => name.replaceAll(".", "[.]");

export default function NetworkCanvas({
  nodes,
  edges,
  onSelect,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onSelect: (id: string | null) => void;
}) {
  const holder = useRef<HTMLDivElement>(null);
  const graph = useRef<Core | null>(null);

  useEffect(() => {
    if (!holder.current) return;
    const elements: ElementDefinition[] = [
      ...nodes.map((n) => ({
        data: { id: n.id, name: defang(n.id), color: colorOf(n.label), scanned: n.role === "scanned" ? 1 : 0 },
      })),
      ...edges.map((e, i) => ({
        data: { id: `e${i}`, source: e.source, target: e.target, color: colorOf(e.sign), inferred: e.inferred ? 1 : 0 },
      })),
    ];
    const cy = cytoscape({
      container: holder.current,
      elements,
      minZoom: 0.3,
      maxZoom: 3,
      wheelSensitivity: 0.2,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            // Names would pile up on a busy map, so only the scanned site and the dot being pointed
            // at or selected show theirs. The list under the map has every name.
            label: "",
            color: COLOR.text,
            "font-size": 9,
            "font-family": "ui-monospace, monospace",
            "text-valign": "bottom",
            "text-margin-y": 4,
            "text-max-width": "110px",
            "text-wrap": "ellipsis",
            width: 16,
            height: 16,
            "border-width": 1,
            "border-color": "#0b1020",
          },
        },
        {
          selector: "node[scanned = 1]",
          style: {
            label: "data(name)",
            width: 30,
            height: 30,
            "border-width": 4,
            "border-color": COLOR.scanned,
            "font-size": 11,
            "font-weight": "bold",
          },
        },
        { selector: "node.pointed", style: { label: "data(name)", "z-index": 10 } },
        { selector: "node:selected", style: { label: "data(name)", "border-width": 3, "border-color": "#ffffff", "z-index": 10 } },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "data(color)",
            "target-arrow-color": "data(color)",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.8,
            "curve-style": "bezier",
            opacity: 0.75,
          },
        },
        { selector: "edge[inferred = 1]", style: { "line-style": "dashed" } },
      ],
      // The scanned site in the middle, its neighbours in rings around it.
      layout: {
        name: "concentric",
        animate: false,
        padding: 28,
        minNodeSpacing: 5,
        avoidOverlap: true,
        concentric: (node: cytoscape.NodeSingular) => (node.data("scanned") ? 2 : 1),
        levelWidth: () => 1,
      } as cytoscape.LayoutOptions,
    });
    cy.on("mouseover", "node", (event) => event.target.addClass("pointed"));
    cy.on("mouseout", "node", (event) => event.target.removeClass("pointed"));
    cy.on("tap", "node", (event) => onSelect(event.target.id()));
    cy.on("tap", (event) => {
      if (event.target === cy) onSelect(null);
    });
    graph.current = cy;
    return () => {
      cy.destroy();
      graph.current = null;
    };
  }, [nodes, edges, onSelect]);

  return (
    <div className="relative">
      <div
        ref={holder}
        role="img"
        aria-label="A map of the scanned site and the sites it is linked with. The list below says the same in words."
        className="relative h-[380px] w-full rounded-xl border border-white/[0.08] bg-ink/60"
      />
      <button
        type="button"
        onClick={() => graph.current?.animate({ fit: { eles: graph.current.elements(), padding: 24 } }, { duration: prefersReducedMotion() ? 0 : 250 })}
        className="absolute right-3 top-3 rounded-md bg-white/10 px-2.5 py-1 text-xs text-slate-100 ring-1 ring-white/15 hover:bg-white/20"
      >
        Fit to view
      </button>
    </div>
  );
}

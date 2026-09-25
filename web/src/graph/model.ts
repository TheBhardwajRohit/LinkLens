// Turns a scan result into a small graph: the redirect chain, the final page, the domains it
// loads from, and anything the sandbox blocked. Also holds the example graph shown before a scan.

import type { Recon, Visit } from "../lib/api";
import { formatAge, NEW_DOMAIN_DAYS } from "../lib/format";

export type NodeKind = "origin" | "hop" | "final" | "domain" | "blocked" | "server";
export type LinkKind = "hop" | "loads" | "blocked" | "hosted";
export type BubbleTone = "white" | "blue" | "red";

export type GraphNode = { id: string; kind: NodeKind };
export type GraphLink = { source: string; target: string; kind: LinkKind };
export type Bubble = { node: string; text: string; tone: BubbleTone };

export type GraphModel = {
  key: string; // changes whenever the graph should rebuild
  nodes: GraphNode[];
  links: GraphLink[];
  chain: string[]; // node ids along the redirect chain, in order
  bubbles: Bubble[];
  mode: "example" | "searching" | "result";
};

const MAX_DOMAINS = 24;
const MAX_BLOCKED = 8;
const MAX_LABEL = 38;

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return url;
  }
}

/** A short, defanged host name that is safe to show in a bubble. */
export function shortHost(host: string): string {
  const safe = host.replaceAll(".", "[.]");
  return safe.length > MAX_LABEL ? `${safe.slice(0, MAX_LABEL - 3)}...` : safe;
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

/** "Hosted in Pune, India · Microsoft" (short, for a bubble). */
function hostingText(recon: Recon): string | null {
  const s = recon.server;
  if (!s || s.status !== "ok") return null;
  const place = s.city && s.country ? `${s.city}, ${s.country}` : s.country;
  const org = s.as_org?.replace(/,? (Inc|LLC|Ltd|Limited|Corporation|Corp|GmbH|B\.V\.|S\.A\.)\.?$/i, "");
  if (!place && !org) return null;
  return [place ? `Hosted in ${place}` : "Hosted", org].filter(Boolean).join(" · ");
}

export function modelFromVisit(visit: Visit, key: string, recon?: Recon): GraphModel {
  // The chain of distinct hosts the link passed through (http -> https on the same host counts once).
  const hosts: string[] = [];
  for (const hop of visit.hops) {
    const h = hostOf(hop.url);
    if (hosts[hosts.length - 1] !== h) hosts.push(h);
  }
  if (hosts.length === 0) hosts.push(hostOf(visit.requested_url));

  const lastHop = visit.hops[visit.hops.length - 1];
  const endBlocked = Boolean(lastHop?.blocked);
  const nodes: GraphNode[] = hosts.map((h, i) => ({
    id: h,
    kind:
      i === hosts.length - 1 ? (endBlocked ? "blocked" : "final") : i === 0 ? "origin" : "hop",
  }));
  const links: GraphLink[] = [];
  for (let i = 1; i < hosts.length; i++) {
    links.push({ source: hosts[i - 1], target: hosts[i], kind: i === hosts.length - 1 && endBlocked ? "blocked" : "hop" });
  }

  const inChain = new Set(hosts);
  const final = hosts[hosts.length - 1];
  const domains = visit.contacted_domains.filter((d) => !inChain.has(d)).slice(0, MAX_DOMAINS);
  for (const d of domains) {
    nodes.push({ id: d, kind: "domain" });
    links.push({ source: final, target: d, kind: "loads" });
  }
  const blockedHosts = [...new Set(visit.blocked.map((b) => b.host))].filter((h) => !inChain.has(h)).slice(0, MAX_BLOCKED);
  for (const b of blockedHosts) {
    nodes.push({ id: `blocked:${b}`, kind: "blocked" });
    links.push({ source: final, target: `blocked:${b}`, kind: "blocked" });
  }

  // The server the final page runs on, from recon.
  const hosting = recon && !endBlocked ? hostingText(recon) : null;
  const serverId = recon?.server?.ip ? `server:${recon.server.ip}` : null;
  if (hosting && serverId) {
    nodes.push({ id: serverId, kind: "server" });
    links.push({ source: final, target: serverId, kind: "hosted" });
  }

  const bubbles: Bubble[] = [];
  const redirects = Math.max(visit.hops.length - 1, 0);
  const age = recon?.registration?.age_days ?? null;
  const young = age !== null && age < NEW_DOMAIN_DAYS ? `, registered ${formatAge(age)} ago` : "";
  if (hosts.length > 1) {
    bubbles.push({ node: hosts[0], text: `You pasted ${shortHost(hosts[0])}`, tone: "white" });
  }
  if (endBlocked) {
    bubbles.push({ node: final, text: `Stopped: ${lastHop?.reason ?? "private address"}`, tone: "red" });
  } else if (visit.stopped === "unreachable") {
    bubbles.push({ node: final, text: `${shortHost(final)} didn't respond${young}`, tone: "white" });
  } else {
    bubbles.push({ node: final, text: `Ends at ${shortHost(final)}${young}`, tone: "blue" });
  }
  if (hosting && serverId) {
    bubbles.push({ node: serverId, text: hosting, tone: "white" });
  }
  if (redirects > 0 && hosts.length > 2) {
    bubbles.push({ node: hosts[1], text: plural(redirects, "redirect"), tone: "white" });
  } else if (redirects > 0 && hosts.length === 1) {
    bubbles.push({ node: final, text: plural(redirects, "redirect"), tone: "white" });
  }
  if (blockedHosts.length > 0) {
    bubbles.push({ node: `blocked:${blockedHosts[0]}`, text: `${plural(visit.blocked.length, "request")} blocked`, tone: "red" });
  }
  if (domains.length > 0) {
    bubbles.push({ node: domains[0], text: `Loads from ${plural(visit.contacted_domains.length, "domain")}`, tone: "white" });
  }

  return { key, nodes, links, chain: hosts, bubbles: bubbles.slice(0, 5), mode: "result" };
}

/** The bubbles to show: only the newest one for each node, so two never sit on the same spot. */
export function visibleBubbles(bubbles: Bubble[]): { bubble: Bubble; index: number }[] {
  const latest = new Map<string, number>();
  bubbles.forEach((b, i) => latest.set(b.node, i));
  return [...latest.values()].sort((a, b) => a - b).map((index) => ({ bubble: bubbles[index], index }));
}

export const BUBBLE_TONE: Record<BubbleTone, string> = {
  white: "[--bubble-bg:#ffffff] [--bubble-fg:#0f172a]",
  blue: "[--bubble-bg:#3b82f6] [--bubble-fg:#ffffff]",
  red: "[--bubble-bg:#f43f5e] [--bubble-fg:#ffffff]",
};

export function searchingModel(url: string, key: string): GraphModel {
  const host = hostOf(url);
  return {
    key,
    nodes: [{ id: host, kind: "origin" }],
    links: [],
    chain: [host],
    bubbles: [{ node: host, text: "Opening it in the sandbox...", tone: "blue" }],
    mode: "searching",
  };
}

// Made-up names on the reserved .example domain, so nothing here points at a real site.
const EX = {
  origin: "short.example",
  hop1: "go.example",
  hop2: "track.example",
  final: "secure-login.example",
};

export const EXAMPLE_MODEL: GraphModel = (() => {
  const nodes: GraphNode[] = [
    { id: EX.origin, kind: "origin" },
    { id: EX.hop1, kind: "hop" },
    { id: EX.hop2, kind: "hop" },
    { id: EX.final, kind: "final" },
  ];
  const links: GraphLink[] = [
    { source: EX.origin, target: EX.hop1, kind: "hop" },
    { source: EX.hop1, target: EX.hop2, kind: "hop" },
    { source: EX.hop2, target: EX.final, kind: "hop" },
  ];
  for (let i = 1; i <= 9; i++) {
    nodes.push({ id: `cdn${i}.example`, kind: "domain" });
    links.push({ source: EX.final, target: `cdn${i}.example`, kind: "loads" });
  }
  for (const b of ["10.0.0.1", "169.254.169.254"]) {
    nodes.push({ id: `blocked:${b}`, kind: "blocked" });
    links.push({ source: EX.final, target: `blocked:${b}`, kind: "blocked" });
  }
  return {
    key: "example",
    nodes,
    links,
    chain: [EX.origin, EX.hop1, EX.hop2, EX.final],
    // Shown one at a time, like a short story, then the loop starts again.
    bubbles: [
      { node: EX.origin, text: "Got this link in a text?", tone: "white" },
      { node: EX.origin, text: "LinkLens opens it for you", tone: "blue" },
      { node: EX.hop1, text: "Redirect 1: a link shortener", tone: "white" },
      { node: EX.hop2, text: "Redirect 2: a tracking page", tone: "white" },
      { node: EX.final, text: "Ends at a fake bank login", tone: "white" },
      { node: "blocked:10.0.0.1", text: "Blocked: it reached for a private address", tone: "red" },
    ],
    mode: "example",
  };
})();

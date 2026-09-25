// Talks to the LinkLens API. VITE_API_URL set to "none" (as on GitHub Pages for now) means
// "no scanner online": the site then makes no requests at all.

const configured = import.meta.env.VITE_API_URL;
export const API_URL: string =
  configured === undefined ? "http://localhost:8000" : configured === "none" ? "" : configured;

// A visit can take up to a minute, plus time waiting for the sandbox to be free.
const SCAN_TIMEOUT_MS = 150_000;

export type Health = {
  status: "ok" | "degraded";
  version: string;
  checks: Record<string, string>;
  keys: Record<string, boolean>;
};

export type HopKind = "start" | "server" | "header" | "meta" | "script" | "form" | "page";

export type Hop = { url: string; kind: HopKind; status: number | null; blocked: boolean; reason: string | null };

export type Visit = {
  requested_url: string;
  final_url: string | null;
  title: string | null;
  status: number | null;
  hops: Hop[];
  blocked: { host: string; port: number; reason: string }[];
  contacted_domains: string[];
  screenshot_jpeg_b64: string | null;
  html_truncated: boolean;
  bot_check: string | null;
  downloads: string[];
  popups: string[];
  pending_refresh: string | null;
  stopped: "timeout" | "blocked" | "unreachable" | "download" | "crashed" | "error" | null;
  notes: string[];
  duration_ms: number;
};

export type Scan = { id: string; url: string; visit: Visit };

export type ScanResult =
  | { kind: "done"; scan: Scan }
  | { kind: "rejected"; error: string }
  | { kind: "unavailable"; error: string }
  | { kind: "offline" };

export async function getHealth(signal?: AbortSignal): Promise<Health | null> {
  if (!API_URL) return null;
  try {
    const resp = await fetch(`${API_URL}/health`, { signal });
    return resp.ok ? ((await resp.json()) as Health) : null;
  } catch {
    return null;
  }
}

async function detail(resp: Response): Promise<string | null> {
  const body = (await resp.json().catch(() => null)) as { detail?: unknown } | null;
  return typeof body?.detail === "string" ? body.detail : null;
}

export async function submitScan(url: string): Promise<ScanResult> {
  if (!API_URL) return { kind: "offline" };
  let resp: Response;
  try {
    resp = await fetch(`${API_URL}/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
      signal: AbortSignal.timeout(SCAN_TIMEOUT_MS),
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "TimeoutError") {
      return { kind: "unavailable", error: "The scan took too long and was stopped. Try again in a minute." };
    }
    return { kind: "offline" };
  }
  if (resp.status === 200) return { kind: "done", scan: (await resp.json()) as Scan };
  if (resp.status === 400) {
    return { kind: "rejected", error: (await detail(resp)) ?? "That link couldn't be read. Check it and try again." };
  }
  if (resp.status === 503) {
    return { kind: "unavailable", error: (await detail(resp)) ?? "The scanner isn't available right now." };
  }
  return { kind: "rejected", error: "Something went wrong on the scanner. Try again." };
}

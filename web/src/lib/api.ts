// Talks to the LinkLens API. VITE_API_URL set to "none" (as on GitHub Pages for now) means
// "no scanner online": the site then makes no requests at all.

const configured = import.meta.env.VITE_API_URL;
export const API_URL: string =
  configured === undefined ? "http://localhost:8000" : configured === "none" ? "" : configured;

export type Health = {
  status: "ok" | "degraded";
  version: string;
  checks: Record<string, string>;
  keys: Record<string, boolean>;
};

export type ScanAccepted = { id: string; status: string; url: string; message: string };

export type ScanResult =
  | { kind: "accepted"; scan: ScanAccepted }
  | { kind: "rejected"; error: string }
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

export async function submitScan(url: string): Promise<ScanResult> {
  if (!API_URL) return { kind: "offline" };
  let resp: Response;
  try {
    resp = await fetch(`${API_URL}/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
  } catch {
    return { kind: "offline" };
  }
  if (resp.status === 202) return { kind: "accepted", scan: (await resp.json()) as ScanAccepted };
  if (resp.status === 400) {
    const body = (await resp.json().catch(() => null)) as { detail?: unknown } | null;
    if (typeof body?.detail === "string") return { kind: "rejected", error: body.detail };
  }
  return { kind: "rejected", error: "The scanner couldn't read that link. Check it and try again." };
}

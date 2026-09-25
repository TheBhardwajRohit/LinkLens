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

export type ReconStatus = "ok" | "not_found" | "not_configured" | "timeout" | "error" | "skipped";

export type Registration = {
  domain: string;
  status: ReconStatus;
  source: "rdap" | "whois" | null;
  registrar: string | null;
  registrar_abuse_email: string | null;
  registrant: string | null;
  created: string | null;
  updated: string | null;
  expires: string | null;
  age_days: number | null;
  nameservers: string[];
  flags: string[];
  dnssec: boolean | null;
  note: string | null;
};

export type DnsRecords = {
  host: string;
  status: ReconStatus;
  a: string[];
  aaaa: string[];
  cname: string[];
  mx: string[];
  ns: string[];
  txt: string[];
  note: string | null;
};

export type ServerInfo = {
  ip: string | null;
  status: ReconStatus;
  country_code: string | null;
  country: string | null;
  city: string | null;
  latitude: number | null;
  longitude: number | null;
  accuracy_km: number | null;
  asn: number | null;
  as_org: string | null;
  network_name: string | null;
  network_range: string | null;
  abuse_email: string | null;
  note: string | null;
};

export type Certificate = {
  host: string;
  protocol: string | null;
  subject: string | null;
  issuer: string | null;
  issuer_org: string | null;
  not_before: string | null;
  not_after: string | null;
  days_left: number | null;
  names: string[];
  self_signed: boolean;
  trusted: boolean;
  problem: string | null;
};

export type CertHistory = {
  domain: string;
  status: ReconStatus;
  source: "crt.sh" | "certspotter" | null;
  cert_count: number;
  first_seen: string | null;
  latest: string | null;
  issuers: string[];
  subdomains: string[];
  other_domains: string[];
  note: string | null;
};

export type HttpInfo = {
  status: ReconStatus;
  server: string | null;
  powered_by: string | null;
  generator: string | null;
  tech: string[];
  security_headers: Record<string, boolean>;
};

export type Recon = {
  host: string | null;
  registered_domain: string | null;
  registration: Registration | null;
  chain_domains: Registration[];
  dns: DnsRecords | null;
  server: ServerInfo | null;
  certificate: Certificate | null;
  cert_history: CertHistory | null;
  http: HttpInfo | null;
  duration_ms: number;
};

export type Verdict = "safe" | "suspicious" | "dangerous";

export type Reason = {
  text: string;
  points: number;
  area: "link" | "page" | "domain" | "certificate" | "server" | "behavior" | "reputation";
};

export type ScamType = { id: string; label: string; brand: string | null; evidence: string[] };

export type Analysis = {
  score: number;
  verdict: Verdict;
  summary: string;
  scam_type: ScamType | null;
  reasons: Reason[];
  good_signs: Reason[];
  partial: boolean;
  tranco_list: string | null;
};

export type Scan = {
  id: string;
  url: string;
  created_at: string;
  visit: Visit;
  recon: Recon;
  analysis: Analysis;
  saved: boolean;
};

export type StepId = "sandbox" | "recon" | "analysis" | "save";
export type StepStatus = "pending" | "running" | "done" | "failed";
export type Step = { id: StepId; label: string; status: StepStatus };

/** Partial data that arrives while a scan runs, so the graph can grow step by step. */
export type Preview = {
  visit?: Pick<Visit, "requested_url" | "final_url" | "hops" | "contacted_domains" | "blocked" | "stopped">;
  server?: ServerInfo | null;
  registration?: Registration | null;
  verdict?: { score: number; verdict: Verdict };
};

export type StartResult =
  | { kind: "started"; id: string; url: string; steps: Step[] }
  | { kind: "rejected"; error: string }
  | { kind: "unavailable"; error: string }
  | { kind: "offline" };

export async function startScan(url: string): Promise<StartResult> {
  if (!API_URL) return { kind: "offline" };
  let resp: Response;
  try {
    resp = await fetch(`${API_URL}/scans`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
  } catch {
    return { kind: "offline" };
  }
  if (resp.status === 202) {
    const body = (await resp.json()) as { id: string; url: string; steps: { id: StepId; label: string }[] };
    return { kind: "started", id: body.id, url: body.url, steps: body.steps.map((s) => ({ ...s, status: "pending" })) };
  }
  if (resp.status === 400 || resp.status === 429) {
    return { kind: "rejected", error: (await detail(resp)) ?? "That link couldn't be scanned." };
  }
  return { kind: "unavailable", error: (await detail(resp)) ?? "The scanner isn't available right now." };
}

type Handlers = {
  onStep: (step: StepId, status: StepStatus, data: Record<string, unknown> | null) => void;
  onDone: (scan: Scan) => void;
  onError: (message: string) => void;
};

/** Follow a running scan's progress. Falls back to asking every few seconds if the stream drops. */
export function followScan(id: string, handlers: Handlers): () => void {
  let finished = false;
  let pollTimer = 0;
  const source = new EventSource(`${API_URL}/scans/${id}/events`);

  const finish = () => {
    finished = true;
    source.close();
    window.clearTimeout(pollTimer);
  };

  source.addEventListener("step", (e) => {
    const d = JSON.parse((e as MessageEvent).data) as { step: StepId; status: StepStatus; data: Record<string, unknown> | null };
    handlers.onStep(d.step, d.status, d.data);
  });
  source.addEventListener("done", (e) => {
    finish();
    handlers.onDone(JSON.parse((e as MessageEvent).data) as Scan);
  });
  source.addEventListener("error", (e) => {
    const data = (e as MessageEvent).data;
    if (typeof data === "string") {
      finish();
      handlers.onError((JSON.parse(data) as { message: string }).message);
      return;
    }
    if (finished) return;
    // The connection dropped: stop the stream and check for the result every few seconds instead.
    source.close();
    const started = Date.now();
    const poll = async () => {
      if (finished) return;
      const scan = await getScan(id);
      if (scan.kind === "found") {
        finish();
        handlers.onDone(scan.scan);
      } else if (Date.now() - started > SCAN_TIMEOUT_MS) {
        finish();
        handlers.onError("Lost touch with the scanner. Try the scan again.");
      } else {
        pollTimer = window.setTimeout(poll, 3000);
      }
    };
    pollTimer = window.setTimeout(poll, 2000);
  });

  return finish;
}

export type GetResult = { kind: "found"; scan: Scan } | { kind: "missing"; error: string } | { kind: "offline" };

export async function getScan(id: string): Promise<GetResult> {
  if (!API_URL) return { kind: "offline" };
  try {
    const resp = await fetch(`${API_URL}/scans/${encodeURIComponent(id)}`);
    if (resp.ok) return { kind: "found", scan: (await resp.json()) as Scan };
    return { kind: "missing", error: (await detail(resp)) ?? "That scan couldn't be found." };
  } catch {
    return { kind: "offline" };
  }
}

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

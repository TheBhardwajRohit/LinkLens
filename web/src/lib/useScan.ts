import { useCallback, useEffect, useRef, useState } from "react";

import { followScan, getHealth, getScan, startScan, type Preview, type Scan, type Step } from "./api";
import { checkUrl } from "./url";

export type ScanState =
  | { kind: "idle" }
  | { kind: "invalid"; error: string }
  | { kind: "loading" } // reopening a saved scan
  | { kind: "sending"; id: string | null; url: string; startedAt: number; steps: Step[]; preview: Preview }
  | { kind: "done"; scan: Scan; refanged: boolean; reopened: boolean }
  | { kind: "rejected"; error: string }
  | { kind: "unavailable"; error: string }
  | { kind: "offline" };

export type ScanControl = {
  state: ScanState;
  online: boolean | null;
  submit: (raw: string) => Promise<void>;
  clearError: () => void;
};

const PARAM = "scan";

/** The address of a saved result, to reopen or share. */
export function resultLink(id: string): string {
  const url = new URL(window.location.href);
  url.search = `?${PARAM}=${encodeURIComponent(id)}`;
  url.hash = "";
  return url.toString();
}

/** Everything about the current scan, shared by the input, the graph, and the report. */
export function useScan(): ScanControl {
  const [state, setState] = useState<ScanState>({ kind: "idle" });
  const [online, setOnline] = useState<boolean | null>(null);
  const stop = useRef<() => void>(() => {});

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal).then((h) => {
      if (!controller.signal.aborted) setOnline(h !== null);
    });
    // Opened from a result link (?scan=...): load that scan.
    const id = new URLSearchParams(window.location.search).get(PARAM);
    if (id) {
      setState({ kind: "loading" });
      getScan(id).then((r) => {
        if (r.kind === "found") setState({ kind: "done", scan: r.scan, refanged: false, reopened: true });
        else if (r.kind === "missing") setState({ kind: "unavailable", error: r.error });
        else setState({ kind: "offline" });
      });
    }
    return () => {
      controller.abort();
      stop.current();
    };
  }, []);

  const submit = useCallback(async (raw: string) => {
    const check = checkUrl(raw);
    if (!check.ok) {
      setState({ kind: "invalid", error: check.error });
      return;
    }
    stop.current();
    const startedAt = Date.now();
    setState({ kind: "sending", id: null, url: check.url, startedAt, steps: [], preview: {} });
    const started = await startScan(check.url);
    if (started.kind !== "started") {
      if (started.kind === "offline") {
        setState({ kind: "offline" });
        setOnline(false);
      } else {
        setState({ kind: started.kind, error: started.error });
      }
      return;
    }
    setOnline(true);
    setState({ kind: "sending", id: started.id, url: started.url, startedAt, steps: started.steps, preview: {} });

    stop.current = followScan(started.id, {
      onStep(step, status, data) {
        setState((s) => {
          if (s.kind !== "sending") return s;
          const steps = s.steps.map((x) => (x.id === step ? { ...x, status } : x));
          const preview = { ...s.preview };
          if (status === "done" && data) {
            if (step === "sandbox") preview.visit = data as Preview["visit"];
            if (step === "recon") {
              preview.server = (data.server as Preview["server"]) ?? null;
              preview.registration = (data.registration as Preview["registration"]) ?? null;
            }
            if (step === "analysis") preview.verdict = data as Preview["verdict"];
          }
          return { ...s, steps, preview };
        });
      },
      onDone(scan) {
        setState({ kind: "done", scan, refanged: check.refanged, reopened: false });
        if (scan.saved) window.history.pushState(null, "", resultLink(scan.id));
      },
      onError(message) {
        setState({ kind: "unavailable", error: message });
      },
    });
  }, []);

  const clearError = useCallback(() => {
    setState((s) => (s.kind === "invalid" || s.kind === "rejected" ? { kind: "idle" } : s));
  }, []);

  return { state, online, submit, clearError };
}

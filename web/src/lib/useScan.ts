import { useCallback, useEffect, useState } from "react";

import { getHealth, submitScan, type Scan } from "./api";
import { checkUrl } from "./url";

export type ScanState =
  | { kind: "idle" }
  | { kind: "invalid"; error: string }
  | { kind: "sending"; url: string; startedAt: number }
  | { kind: "done"; scan: Scan; refanged: boolean }
  | { kind: "rejected"; error: string }
  | { kind: "unavailable"; error: string }
  | { kind: "offline" };

export type ScanControl = {
  state: ScanState;
  online: boolean | null;
  submit: (raw: string) => Promise<void>;
  clearError: () => void;
};

/** Everything about the current scan, shared by the input, the graph, and the report. */
export function useScan(): ScanControl {
  const [state, setState] = useState<ScanState>({ kind: "idle" });
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal).then((h) => {
      if (!controller.signal.aborted) setOnline(h !== null);
    });
    return () => controller.abort();
  }, []);

  const submit = useCallback(async (raw: string) => {
    const check = checkUrl(raw);
    if (!check.ok) {
      setState({ kind: "invalid", error: check.error });
      return;
    }
    setState({ kind: "sending", url: check.url, startedAt: Date.now() });
    const result = await submitScan(check.url);
    if (result.kind === "done") {
      setState({ kind: "done", scan: result.scan, refanged: check.refanged });
      setOnline(true);
    } else if (result.kind === "rejected" || result.kind === "unavailable") {
      setState({ kind: result.kind, error: result.error });
    } else {
      setState({ kind: "offline" });
      setOnline(false);
    }
  }, []);

  const clearError = useCallback(() => {
    setState((s) => (s.kind === "invalid" || s.kind === "rejected" ? { kind: "idle" } : s));
  }, []);

  return { state, online, submit, clearError };
}

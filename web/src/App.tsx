import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type Health = {
  status: "ok" | "degraded";
  version: string;
  checks: Record<string, string>;
  keys: Record<string, boolean>;
};

type State = { kind: "loading" } | { kind: "down" } | { kind: "up"; health: Health };

function Dot({ ok }: { ok: boolean }) {
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${ok ? "bg-emerald-400" : "bg-rose-500"}`} />;
}

function Row({ label, ok, text }: { label: string; ok: boolean; text: string }) {
  return (
    <li className="flex items-center justify-between gap-4 py-2">
      <span className="text-slate-400">{label}</span>
      <span className="flex items-center gap-2 text-slate-200">
        <Dot ok={ok} />
        {text}
      </span>
    </li>
  );
}

export default function App() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_URL}/health`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((health: Health) => setState({ kind: "up", health }))
      .catch((err: unknown) => {
        if (!(err instanceof DOMException && err.name === "AbortError")) setState({ kind: "down" });
      });
    return () => controller.abort();
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 py-16">
      <h1 className="bg-linear-to-r from-cyan-300 to-sky-500 bg-clip-text text-5xl font-bold tracking-tight text-transparent sm:text-7xl">
        LinkLens
      </h1>
      <p className="mt-4 text-center text-lg text-slate-300">Paste a link. See who's really behind it.</p>
      <p className="mt-2 text-sm text-slate-500">Under construction. The real homepage arrives in phase 1.</p>

      <section className="mt-10 w-full max-w-sm rounded-xl border border-line bg-panel p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">System status</h2>
        {state.kind === "loading" && <p className="mt-3 text-slate-400">Checking the API...</p>}
        {state.kind === "down" && (
          <ul className="mt-2 divide-y divide-line">
            <Row label="API" ok={false} text="not reachable" />
          </ul>
        )}
        {state.kind === "up" && (
          <>
            <ul className="mt-2 divide-y divide-line">
              <Row label="API" ok text={`ok (v${state.health.version})`} />
              {Object.entries(state.health.checks).map(([name, value]) => (
                <Row key={name} label={name[0].toUpperCase() + name.slice(1)} ok={value === "ok"} text={value} />
              ))}
            </ul>
            <p className="mt-4 text-xs text-slate-500">
              Keys set:{" "}
              {Object.entries(state.health.keys)
                .filter(([, set]) => set)
                .map(([name]) => name)
                .join(", ") || "none"}
            </p>
          </>
        )}
      </section>
    </main>
  );
}

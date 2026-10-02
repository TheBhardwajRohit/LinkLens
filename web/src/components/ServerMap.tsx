// "Where the server is": a pin on a world map. The map is only loaded when asked for, because
// its tiles come from OpenStreetMap's servers (the one place this site talks to a third party).

import { MapPin } from "lucide-react";
import { lazy, Suspense, useState } from "react";

import type { ServerInfo } from "../lib/api";
import Guard from "./Guard";

const ServerMapCanvas = lazy(() => import("./ServerMapCanvas"));

export default function ServerMap({ server }: { server: ServerInfo | null }) {
  const [open, setOpen] = useState(false);
  if (!server || server.latitude === null || server.longitude === null) return null;
  const place = [server.city, server.country].filter(Boolean).join(", ") || "the server's location";

  if (!open) {
    return (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-white/[0.08] bg-ink/30 px-4 py-3 text-sm">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-white/[0.06] px-3 py-1.5 text-slate-100 ring-1 ring-white/10 transition hover:bg-white/10"
        >
          <MapPin className="h-4 w-4 text-blue-400" aria-hidden="true" />
          Show {place} on a map
        </button>
        <span className="text-xs text-slate-500">
          Map tiles load from OpenStreetMap, which will see your IP address.
        </span>
      </div>
    );
  }
  return (
    <div>
      <Guard name="server map">
        <Suspense fallback={<div className="h-[260px] rounded-xl border border-white/[0.08] bg-ink/60" />}>
          <ServerMapCanvas lat={server.latitude} lon={server.longitude} accuracyKm={server.accuracy_km} />
        </Suspense>
      </Guard>
      <p className="mt-1 text-xs text-slate-500">
        The pin is where MaxMind's data places the server's address
        {server.accuracy_km ? `, give or take ${server.accuracy_km} km` : ""}. It is where the server is, not
        necessarily where the people behind the site are.
      </p>
    </div>
  );
}

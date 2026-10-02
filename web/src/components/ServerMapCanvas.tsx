// The map itself (Leaflet with OpenStreetMap tiles). Loaded only after the visitor asks for it.

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useRef } from "react";

const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

export default function ServerMapCanvas({ lat, lon, accuracyKm }: { lat: number; lon: number; accuracyKm: number | null }) {
  const holder = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!holder.current) return;
    const map = L.map(holder.current, { scrollWheelZoom: false, attributionControl: true }).setView([lat, lon], 4);
    L.tileLayer(TILES, {
      maxZoom: 12,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
    }).addTo(map);
    // A dot instead of the default pin image, and a circle for how rough the location is.
    if (accuracyKm) {
      L.circle([lat, lon], { radius: accuracyKm * 1000, color: "#3b82f6", weight: 1, fillOpacity: 0.12 }).addTo(map);
    }
    L.circleMarker([lat, lon], { radius: 7, color: "#ffffff", weight: 2, fillColor: "#3b82f6", fillOpacity: 1 }).addTo(map);
    return () => {
      map.remove();
    };
  }, [lat, lon, accuracyKm]);

  return <div ref={holder} className="h-[260px] w-full rounded-xl border border-white/[0.08]" />;
}

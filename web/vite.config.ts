import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

// Adds a Content Security Policy to the built page. The browser then refuses any script, style,
// or connection we didn't list, which blocks most injected code. Build only: the dev server
// needs inline scripts for live reload.
function contentSecurityPolicy(): Plugin {
  return {
    name: "linklens-csp",
    apply: "build",
    transformIndexHtml(html) {
      const api = process.env.VITE_API_URL ?? "http://localhost:8000";
      const apiOrigin = api && api !== "none" ? new URL(api).origin : "";
      const connect = ["'self'", apiOrigin].filter(Boolean).join(" ");
      // Thumbnails of known pages are small JPEGs served by our own API. The server map's tiles
      // come from OpenStreetMap, and only after the visitor clicks "Show on a map".
      const images = ["'self'", "data:", apiOrigin, "https://tile.openstreetmap.org"].filter(Boolean).join(" ");
      const policy = [
        "default-src 'self'",
        "script-src 'self'",
        // The hash allows exactly one inline style: the one-line rule Cytoscape.js (network map) adds,
        // ".__________cytoscape_container { position: relative; }". Nothing else inline is allowed.
        "style-src 'self' 'sha256-pgvDUBa4IjFA2yuSJ2cqcyxmNYJMborsd0ORcRv9vw8='",
        `img-src ${images}`,
        "font-src 'self'",
        `connect-src ${connect}`,
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
      ].join("; ");
      const charset = '<meta charset="UTF-8" />';
      return html.replace(charset, `${charset}\n    <meta http-equiv="Content-Security-Policy" content="${policy}" />`);
    },
  };
}

// VITE_BASE is "/LinkLens/" when building for GitHub Pages, "/" everywhere else.
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  plugins: [react(), tailwindcss(), contentSecurityPolicy()],
  server: { port: 5173 },
  // The three.js chunk is about 900 kB but loads lazily, after the page is already on screen.
  build: { chunkSizeWarningLimit: 1000 },
});

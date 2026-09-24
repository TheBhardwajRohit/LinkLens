import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// VITE_BASE is "/LinkLens/" when building for GitHub Pages, "/" everywhere else.
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
});

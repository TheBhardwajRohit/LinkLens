# Tech decisions

Every stack choice, and the reason for it. At the end of the project, this file is the answer to "why this stack?".

**Status:** *Decided* = agreed with Rohit (2026-09-24).

| # | Area | Choice | Why | Alternatives considered | Status |
|---|---|---|---|---|---|
| 1 | Website hosting | GitHub Pages | Free, lives in the same repo, and Rohit wanted GitHub. Static files only, which fits because our backend is separate. | Vercel, Netlify (also free, but another account) | Decided |
| 2 | Scheduled jobs | GitHub Actions | Free and in the repo (public repo, so no minute limit on standard runners). Each run gets a fresh throwaway VM, which is a safe, isolated place to visit scam pages (safety rule 10). GitHub's terms make data-collecting cron a gray area; Rohit accepted that risk. | Cron on a VM, Celery beat | Decided |
| 3 | Database + screenshots | Supabase (free plan) | A real Postgres database (what the plan needs), plus file storage for screenshots and a read-only API the static website can use. All in one free account. | Neon (Postgres only, no file storage); JSON files in the git repo (size limits, every save is a commit, parallel jobs clash) | Decided, account not created yet |
| 4 | Live scan server | Docker containers, on Rohit's PC for now | GitHub can't run a server, and Actions' terms forbid using it as part of a serverless app. Containers move to any host unchanged, so the host can be picked later. | Free cloud hosts, to compare in phase 10 | Decided for now; host still open |
| 5 | Website framework | Vite + React + TypeScript | The site is a static single-page app talking to a separate API. Next.js's main extras (server rendering, API routes) don't work on GitHub Pages, so Vite gives the same React ecosystem with less setup. | Next.js static export (works, but most of its features go unused); Astro | Decided |
| 6 | Styling and motion | Tailwind CSS, Motion (the new name of Framer Motion) | Fast to build a consistent dark theme; smooth card animations, scroll effects, and tilt, with built-in reduced-motion support. | Plain CSS, GSAP | Decided |
| 7 | 3D hero | react-three-fiber (Three.js) | The standard way to do WebGL in React; easy to lower quality on weak devices. | Plain Three.js, canvas 2D | Decided |
| 8 | Maps and graphs | Cytoscape.js (network map), Leaflet + OpenStreetMap (server map) | Both free, no API keys, and built for exactly these jobs. | D3 force graph, Mapbox (needs a key) | Decided |
| 9 | API | Python + FastAPI | Python has the analysis libraries we need (TLSH, pHash, DNS, graphs, ML). FastAPI handles many lookups at once (async), checks inputs, and supports live progress. | Node + Express (weaker analysis libraries), Django (heavier) | Decided |
| 10 | Sandbox browser | Playwright + Chromium, own container | Records redirects, every network request, and screenshots. Well maintained, with a Python API. | Puppeteer (Node only), Selenium (less network detail) | Decided |
| 11 | Job queue | None at first (no Celery, no Redis) | Scheduled work runs on Actions. The scan server has one user and low volume, so FastAPI background tasks are enough. Fewer containers also make free hosting easier. Add arq or RQ with Redis if scans start piling up. | Celery + Redis (from the original brief) | Decided |
| 12 | Live progress | Server-Sent Events | One-way updates from server to browser. Simpler than WebSockets, and works over plain HTTP. | WebSockets, polling | Decided |
| 13 | Local dev database | Postgres in Docker | Tests run offline, without touching shared data or free quotas. It's the same Postgres Supabase uses. | Supabase CLI local stack (many containers) | Decided |
| 14 | Icons | lucide-react | Clean, consistent line icons; only the ones we use end up in the bundle. | Hand-drawn SVGs, Heroicons | Decided |
| 15 | Fonts | Space Grotesk (headings), Inter (text), self-hosted via Fontsource | Self-hosting means no requests to Google Fonts, so visitors aren't tracked and the security policy stays strict. | Google Fonts CDN, system fonts | Decided |
| 16 | Website tests | Vitest | Built for Vite, so tests reuse the same config and run in under a second. | Jest (needs extra setup with Vite) | Decided |
| 17 | Page security | Content Security Policy added at build time | The browser refuses any script, style, or connection we didn't list, which blocks most injected code. This matters most in phase 4, when results from scam pages are shown. | No policy (GitHub Pages can't set security headers, so a meta tag is the only option) | Decided |
| 18 | 3D loading | three.js loaded lazily, with an error guard and a frame-rate check | three.js is about 240 kB compressed. Loading it after the page appears keeps the first paint fast. If it fails or runs under 24 frames a second, the page quietly switches to a static gradient. | Always load 3D; CSS-only background | Decided |

## Sources we chose not to use

| Source | Why not |
|---|---|
| OpenPhish academic feed | Approval is slow and access is time-limited. Rohit's choice: skip it. |
| PhishTank | New user registration has been closed since 2020. |

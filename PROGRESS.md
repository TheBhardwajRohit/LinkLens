# Progress

Each phase ends in a working state. The next phase starts only after Rohit says "go".

## Setup (2026-09-24)

- [x] Brief saved to `docs/PROJECT_BRIEF.md`, condensed into `CLAUDE.md`
- [x] Environment checked: Windows 11, Git 2.51, Docker 29.7 + Compose v5.5, Node 24.11, Python 3.12 / 3.13, WSL2 Ubuntu
- [x] Hosting and storage decided (GitHub Pages + Actions, Supabase, scan server in Docker)
- [x] Google Safe Browsing key saved in `.env` and tested (test URL flagged as MALWARE)
- [x] Dataset research written to `docs/DATASETS.md`
- [x] `.gitignore`, `.env.example`, `docs/TECH_DECISIONS.md` created
- [x] Docker Desktop engine running, GitHub CLI installed

## Phase 0 checklist

- [x] Git repo, commits as TheBhardwajRohit (noreply email)
- [x] `api/`: FastAPI `/health` (database, sandbox, key names only) + 4 tests
- [x] `sandbox/`: placeholder service with health route + 1 test
- [x] `web/`: Vite + React + TS + Tailwind placeholder with live status card
- [x] `docker-compose.yml`: web, api, sandbox, db; sandbox isolated (checked it can't reach the DB by name or IP)
- [x] CI workflow: API tests, sandbox tests, web build, full stack health check, isolation check
- [x] README
- [x] GitHub repo created and pushed: https://github.com/TheBhardwajRohit/LinkLens
- [x] CI passes on GitHub (all 4 jobs green)

## Phase 1 checklist

- [x] MIT license
- [x] 3D background: 4 depth layers, glowing dots, a few pulsing red ones, drift, mouse and scroll parallax
- [x] Falls back to a static gradient on weak devices, low frame rate, or any 3D error (error case checked in the browser)
- [x] Reduced motion: scene renders once and stays still; cards don't float or tilt (code path in place; the browser pane can't emulate this setting, so not checked live)
- [x] Hero: name, tagline, "Scan a link" button that scrolls to the input and focuses it
- [x] 10 feature cards at 3 depths, float, scroll parallax, tilt on hover (mouse only)
- [x] URL input: adds https, refangs, rejects non-web schemes, local and private addresses; 31 tests
- [x] API `POST /scan` placeholder with the same rules; 31 tests (35 API tests total)
- [x] Checked on desktop and phone (375 px wide) in the browser pane
- [x] Content Security Policy on the built site, no violations
- [x] Live on GitHub Pages: https://thebhardwajrohit.github.io/LinkLens/ (shows "scanner offline", makes no API calls)
- [x] Commits carry no Claude attribution; history rewritten to remove the earlier co-author lines

## Phase 2 checklist

- [x] SSRF guard (`sandbox/app/guard.py`): looks up every host, allows only public addresses; blocks private, local, cloud metadata, reserved, IPv6 forms hiding IPv4, odd number forms like `2130706433`, and non-web ports
- [x] Filtering proxy (`sandbox/app/proxy.py`): every browser connection goes through it; connects to the exact IP the guard checked (stops DNS rebinding); caps connections and bytes; logs contacted domains
- [x] Sandbox browser (`sandbox/app/visit.py`): Playwright 1.63 + Chromium; redirect chain (server, Refresh header, meta, script, page-submitted form), final address, screenshot, HTML, title
- [x] Never types, clicks, submits, or downloads; dialogs dismissed, popups closed, service workers blocked, UDP off; bot checks detected, never bypassed; hard time limits; one visit at a time
- [x] API `/scan` hands the link to the sandbox and drops captured HTML before replying
- [x] Website shows the outcome, screenshot, final address, link trail, blocked requests, contacted domains (all defanged, copy button)
- [x] 85 sandbox tests, run in the real image with networking off; 39 API tests; 31 website tests
- [x] Live check: example.com and github.com captured; localtest.me (DNS points at 127.0.0.1) and 169.254.169.254.nip.io (cloud metadata) blocked
- [x] CI: sandbox tests in the image offline, plus a real scan of example.com and a blocked localtest.me in the full-stack job

## Phases

| # | What | Done when | Status |
|---|---|---|---|
| 0 | Repo, Docker Compose skeleton, `.env.example`, README, CLAUDE.md, PROGRESS.md, CI workflow | `docker compose up` shows a placeholder page and the API health check passes | Done |
| 1 | Homepage UI (3D hero, name, feature cards, URL input) + API stub | Looks right on desktop and mobile; input validates URLs and calls the stub | Done |
| 2 | Safe fetching: SSRF guard, sandbox, redirect chain, screenshot | A scan returns screenshot + redirect chain; private IPs blocked (with tests) | Done |
| 3 | Recon: RDAP, DNS, GeoIP/ASN, TLS, CT, headers | Recon panel shows real data for a test domain | Plan proposed |
| 4 | Analysis v1: lexical + content features, scam type rules, rule-based score, reasons; live progress; results page v1 | Full scan flow works end to end with plain-language reasons | Not started |
| 5 | Blacklist integrations with caching and quota handling | Each service shows a result or a clear "not configured / quota reached" | Not started |
| 6 | Data: dataset loaders, fingerprinting, cron feed ingestion (GitHub Actions) | Datasets loaded; feeds ingest on schedule; admin view shows ingestion health | Not started |
| 7 | Nightly family clustering, Family Finder, 4 sibling tabs | A scanned page matches a family when a similar page exists | Not started |
| 8 | SiNMULI graph module + network map | Local signed graph built, signs inferred, unknown neighbors labeled, map renders | Not started |
| 9 | ML scoring (LightGBM) combined with rules; evaluation on a held-out set | Precision/recall report written to `docs/`; score uses the model | Not started |
| 10 | Extras: PDF report, trends dashboard, feedback button, bulk scan, API keys for our API, rate limiting, deploy scan server to a free host | Each feature works and is documented | Not started |

## Log

- **2026-09-24:** Project set up. Repo public from day one; Rohit has the Student Developer Pack; Actions will run the cron jobs.
- **2026-09-24:** Phase 0 built. `docker compose up` serves the placeholder on :3000 and `/health` reports database ok, sandbox ok, Safe Browsing key set.
- **2026-09-24:** Removed Claude co-author lines from all commits (history rewritten, force-pushed by Rohit). No attribution from now on.
- **2026-09-24:** Phase 1 built. Homepage live on GitHub Pages. Local stack scans reach the `/scan` placeholder.
- **2026-09-25:** Phase 2 built. Real scans on the local stack (http://localhost:3000). The live Pages site still shows "scanner offline" by design until a public scan server exists.

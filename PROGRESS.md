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

## Homepage redesign (between phases 2 and 3)

- [x] OneText-inspired split hero: heading, glass input, blue Scan button, trust line (left 60%); live 3D graph (right 40%)
- [x] Graph plays a looping example story in speech bubbles before a scan, pulses during a scan, and draws the real result after (chain, loaded domains, blocked hosts)
- [x] Glossy nodes and rails with packets rolling along the redirect chain; flat SVG fallback for no WebGL, crashes, or slow devices (checked with WebGL turned off)
- [x] Slim top bar, overlapping safety panel, glass feature cards with hover glow and honest Live / Coming soon badges
- [x] Full-page 3D background removed; fonts now Red Hat Display and Red Hat Text
- [x] Checked at 1440 px and 390 px wide, plus real scans of github.com and localtest.me (blocked)
- [x] 8 new graph tests (39 website tests in total)
- [x] MaxMind account ID and license key saved in `.env`; download auth checked OK

## Phase 3 checklist

- [x] Domain registration: RDAP via IANA bootstrap (registrar, dates, age, name servers, flags, DNSSEC, registrar abuse contact); WHOIS fallback for TLDs without RDAP (.io, .co)
- [x] Registration age for every other domain in the link trail
- [x] DNS: A, AAAA, CNAME, MX, NS, TXT; public resolvers first; partial results when one record type stalls
- [x] Server: MaxMind GeoLite2 City + ASN (local files, weekly refresh, HEAD check first) plus IP RDAP for network name and abuse contact; uses the IP the sandbox actually connected to; private IPs never looked up
- [x] TLS certificate captured by the sandbox through the guard: issuer, validity, days left, names, trusted or not (and why)
- [x] Certificate history: crt.sh, with Cert Spotter as the backup (crt.sh was down all day while building this)
- [x] HTTP headers (cookie values dropped) and tech detection: hosting/CDN, server software, site builders, security headers
- [x] Report: "Who's behind it" cards (Server, Domain, Certificate) + DNS and headers sections; graph gains a server node with a "Hosted in ..." bubble; brand-new domains called out
- [x] Server Tracker card now Live; GeoLite2 attribution in the footer and README
- [x] Tests: 71 API (all sources on saved samples or fakes), 90 sandbox (incl. a self-signed HTTPS fixture), 45 website
- [x] Live check: github.com (MarkMonitor, 2007, Pune / Microsoft AS8075, trusted Sectigo cert) and example.com; CI checks example.com recon and that missing MaxMind keys degrade gracefully

## Phase 4 checklist

- [x] Link checks: lookalikes (typos, digit swaps, letters from other alphabets, brand plus extra words, brand in front of another domain), IP hosts, @ tricks, odd ports, free hosting, abused TLDs, random-looking names, scammy words, shorteners
- [x] Page checks (server side only): sensitive fields (password, card, CVV, OTP, UPI PIN, ATM PIN, Aadhaar, PAN, net banking, recovery phrase), forms posting elsewhere, brand names on the wrong site, wallets, pressure/prize/job/tech-support/government/shopping/crypto/download wording, hidden frames, blocked right-click, scrambled code, empty links
- [x] Brand list (60+ global and Indian brands); .bank.in and .gov.in treated as official
- [x] Tranco top 100k as a popularity signal (downloaded into a volume, refreshed monthly)
- [x] Scam types by rules: banking, fake login, crypto, prize, shop, tech support, malware, job, government
- [x] Rule-based score 0 to 100 with plain reasons and good signs; blocked private-address links at least Suspicious
- [x] Every scan saved in Postgres; personal data removed from stored and shared links
- [x] Live progress over Server-Sent Events, with a polling fallback; per-network rate limit
- [x] Website: live step checklist, graph grows per step and ends with a colored verdict bubble, verdict card, "Why we flagged it", coming-soon list, shareable `?scan=` links that reopen saved results
- [x] Tests: 122 API (made-up scam pages for every type), 48 website, 90 sandbox
- [x] Live check: github.com Safe 0/100 (Tranco #29, 18 years old), localtest.me Suspicious 40/100, reopened from its link; CI checks the stream, saving, and redaction

## Phases

| # | What | Done when | Status |
|---|---|---|---|
| 0 | Repo, Docker Compose skeleton, `.env.example`, README, CLAUDE.md, PROGRESS.md, CI workflow | `docker compose up` shows a placeholder page and the API health check passes | Done |
| 1 | Homepage UI (3D hero, name, feature cards, URL input) + API stub | Looks right on desktop and mobile; input validates URLs and calls the stub | Done |
| 2 | Safe fetching: SSRF guard, sandbox, redirect chain, screenshot | A scan returns screenshot + redirect chain; private IPs blocked (with tests) | Done |
| 3 | Recon: RDAP, DNS, GeoIP/ASN, TLS, CT, headers | Recon panel shows real data for a test domain | Done |
| 4 | Analysis v1: lexical + content features, scam type rules, rule-based score, reasons; live progress; results page v1 | Full scan flow works end to end with plain-language reasons | Done |
| 5 | Blacklist integrations with caching and quota handling | Each service shows a result or a clear "not configured / quota reached" | Plan proposed |
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
- **2026-09-25:** Homepage redesigned (OneText-inspired split hero with a live scan graph). MaxMind key added.
- **2026-09-25:** Phase 3 built. Recon adds about 3 seconds to a scan.
- **2026-09-25:** Phase 4 built. Scans give a verdict, a score, a scam type, and plain reasons; progress streams live; results are saved and reopen from a link.

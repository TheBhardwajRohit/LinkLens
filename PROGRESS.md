# Progress

Each phase ends in a working state. Phases 0 to 4 each started after Rohit said "go". On 2026-10-02 Rohit said to keep building through the remaining phases without stopping.

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

## Phase 5 checklist

- [x] Google Safe Browsing (Lookup API v4): the pasted link, the final page, and every stop in between, in one request; key sent in a header so it can't leak into logs
- [x] Phishing.Database lists (about 59,000 links and 392,000 domains) downloaded into a Docker volume, refreshed every 6 hours, and checked locally without sending anything out
- [x] urlscan.io search without a key: whether others have scanned the site before (only the site name is sent)
- [x] VirusTotal and URLhaus built and tested against stand-ins; they show "not set up" until a free key is added to `.env`
- [x] LinkLens history: earlier scans of the same domain
- [x] Every source ends with a plain status: listed, not listed, never seen, not set up, limit reached, no answer
- [x] Cache in memory and in Postgres (`lookup_cache`); VirusTotal kept inside 4 checks a minute
- [x] Quick first answer: blacklists run before the sandbox (about 2 seconds), then again for the real destination
- [x] Listings add to the score with the source named ("Google Safe Browsing lists this link as suspected phishing")
- [x] Report: "Blacklist results" section with Google's required attribution and notice; "Listed by" line on the verdict card
- [x] Fixed: readable names like `sbi-kyc-update` were called "randomly generated"; an incomplete saved scan could blank the report page
- [x] Tests: 156 API, 53 website, 90 sandbox
- [x] Live check: Google's official test address (`malware.testing.google.test`) comes back "Likely dangerous, listed by Google Safe Browsing"; github.com stays Safe

## Phase 6 checklist

- [x] Fingerprints for every scanned page: TLSH of the HTML, exact and similarity hashes of the tag structure, a similarity hash of the words, pHash of the screenshot, and the favicon hash
- [x] Sandbox captures the site icon in a second tab, through the same proxy and SSRF guard (95 sandbox tests)
- [x] Page library (`pages` table): fingerprints, a few facts for finding siblings, a small thumbnail. Raw HTML is never stored
- [x] Dataset loader: streams PhreshPhish straight from Hugging Face, keeps fingerprints and feature numbers, throws the HTML away. Loaded locally: 39,522 training pages (17,807 scam, 21,715 honest) and 15,558 test pages (7,043 scam, 8,515 honest)
- [x] Feed ingestion as three GitHub Actions jobs (plan, visit with no secrets, store). Checked with a manual dry run on GitHub: 6 feed links visited in the runner, 1 still live, nothing stored
- [x] Hourly schedule in place but switched off until a shared database exists (`INGEST_ENABLED` variable)
- [x] `GET /stats` and the "What LinkLens knows" section on the site (the data health view)
- [x] Found on the way: the dataset's files hold thousands of pages in one block, which ran the first loader out of memory three times. The loader now reads them directly in small batches (peak about 3 GB instead of over 7 GB)
- [x] Decision changed: no keep-alive for scheduled workflows (GitHub took down the best-known one for breaking its terms)
- [ ] Not done: loading into Supabase (needs the account), Phishpedia and Zenodo screenshot sets (not needed yet)

## Phase 7 checklist

- [x] One rule for "same design", used everywhere: at least two kinds of fingerprint must agree, and one of them must be about what the page says or shows (builder platforms like Wix give unrelated pages the same code)
- [x] Family grouping job (`jobs/cluster.py`, nightly workflow `cluster.yml`): 531 families holding 6,673 of 55,084 pages, in about 12 seconds
- [x] Checked against the dataset's own brand labels: 92% of a family's branded pages share the family's brand (weighted by size). Examples: "fake Meta login page" (286 pages on 248 sites), "fake Booking page", "fake USPS page", "fake MetaMask page"
- [x] Standard notices (suspended, parked, not found) and groups aimed at many different brands are kept out of families
- [x] Family Finder in the scan: 200 real scam pages were looked up with their own site left out; 186 (93%) landed in their own family, none in a wrong one. Of 300 honest pages, none matched a scam family (2 got a weaker "similar" or "copy" note). A lookup takes about 20 ms
- [x] Sibling Hunter with 4 tabs: same server, same owner, same design, lookalike names (checked in DNS, never visited)
- [x] Report: family card ("Family #12: fake SBI login page, 43 pages on 30 sites, first seen 3 Sept"), sibling tabs, thumbnails from our own screenshots
- [x] Family and sibling matches add to the score, except for a brand's real site or a very popular site

## Phase 8 checklist

- [x] Link graph after the SiNMULI paper (read on arXiv): sites as nodes, links as edges signed by the site they start at, the balance rule for unknown signs in triangles, then the 51% vote over incoming links
- [x] Built only around the scanned site (who it links to, who links to it, links among those), from the page library
- [x] Abstains when links are few or disagree, and says so. Live check: github.com is called honest because 67 of 118 known sites linking to it are honest
- [x] Being linked from scam sites, or linking to them, adds to the score; being linked from honest sites is a good sign
- [x] Network map (Cytoscape.js): red for known scams, green for known honest sites, grey for unknown; drag, zoom, click; the same content as a plain list underneath
- [x] Server map (Leaflet + OpenStreetMap), loaded only after a click because the tiles come from a third party
- [x] Tests: 225 API, 14 jobs, 95 sandbox, 58 website

## Phase 9 checklist

- [x] Feature list for the model: 78 numbers read from the link and the page. Popularity, the query string, and "is on free hosting" are left out on purpose
- [x] Training job (`jobs/train.py`): LightGBM, 200 trees, trained on 33,593 pages; the newest 15% of the training pages decide when to stop
- [x] Checked on 15,558 pages the model never saw (the dataset's own, later test split): ROC AUC 0.9743. At the 50% cut-off it catches 75.9% of the scam pages, 97.5% of what it flags really is a scam, and it wrongly flags 1.6% of honest pages
- [x] Found and fixed: the first model had learned shortcuts from the way the dataset was collected (a query string, a bare site address, a small page, and free hosting each "meant" scam). On 63 real honest pages it called all 63 likely scams once a newsletter tag was added to the link. Now the model never sees the query string or free hosting, honest pages count for more in training where they are rare, and the model cannot raise a verdict alone
- [x] The model's limit: it counts in full only when the plain rules already scored 8 or more, not counting the points for free hosting. Alone it adds at most 20 points and never lifts a page out of Safe. On a free hosting service it never adds more than 20, backed or not (it has seen 65 honest pages hosted that way against 5,448 scam pages). It never marks down a brand's real site or a top-10,000 site, and it says nothing on a bot-check screen
- [x] Real-site check (`jobs/honest_check.py`): 126 well-known honest pages from outside the dataset (small sites, login pages, pages on free hosting, Indian government services), scanned through the local scan server. Rated 60% or more likely scam by the model alone: 13. Above Safe in a scan: 1 (without the limits: 5). The training job repeats this check every time
- [x] What the limit costs, measured: on the dataset, rules plus model mark 41.2% of scam pages Suspicious or worse and 1.0% of honest pages (rules alone: 6.1% and 1.6%). Without the limit it would be 63.1%, but a dataset has no domain age, certificate, blacklist, or family for the rules to use; a live scan does
- [x] Four rule fixes the real-site check led to: a site on a free hosting service is no longer judged by that service's domain age, certificate, or owner record (github.io is 13 years old whoever made the page); scam phrases such as "immediately" or "virus" no longer score on pages of 600 words or more, where the training data shows they are ordinary language; 16 brands' verified GitHub organisations are recognised as theirs (google.github.io is not a Google lookalike); and the headline no longer says "no warning signs" above a list that has some
- [x] Report written to `docs/MODEL_REPORT.md` (data, what the dataset gets wrong, results by cut-off and by page size, rules against rules plus model, the real-site check, what the model leans on, honest limits)
- [x] The model ships as plain JSON and runs in about 40 lines of Python in the API. The training job fails if that runner and LightGBM disagree, and a test fails if the model and the feature list drift apart
- [x] Each prediction names the features that pushed it most, in plain words, and becomes one reason in the score
- [x] A false-alarm rule fixed on the way: "shows a brand's name but isn't the brand's site" fired on honest sites with a Facebook link or a "Sign in with Google" button; it now needs the page to be mostly about that one brand
- [x] A scoring gap closed on the way: good signs could pull a blacklisted link down to Safe. An exact listing (Google Safe Browsing, the exact link on Phishing.Database, 5 or more VirusTotal vendors, a live URLhaus entry) is now always Likely dangerous, and a weaker listing is never Safe

## Phase 10 checklist

- [x] Download report: a print layout of the report; the browser's print window saves it as a PDF (5 pages for a typical scan)
- [x] Report a mistake: a short form stored with the scan; email addresses are removed from the note; 10 an hour per network
- [x] Bulk scan: up to 10 links, run one after another, each with its verdict and a link to its report
- [x] Trends: scans per day by verdict, kinds of scam, the brands copied most, the biggest families (`GET /trends`)
- [x] API keys for scripts (`python -m app.access create "name"`): shown once, stored only as hashes, each with its own hourly limit; the scanner can be closed to callers without a key
- [x] Rate limits that work behind a cloud host's proxy (`TRUST_FORWARDED_FOR`)
- [x] Screenshots older than 90 days are dropped; the thumbnail and fingerprints stay
- [x] Workflow that publishes the two containers, and a step-by-step guide for putting everything online for free (`docs/DEPLOY.md`)
- [ ] Not done, needs Rohit's accounts: creating the Supabase project, switching on the hourly jobs, and deploying the scan server to Azure. The guide's Azure commands follow Microsoft's docs but have not been run on a real subscription
- [x] Tests: 255 API, 24 jobs, 95 sandbox, 61 website. CI green on GitHub

## Phases

| # | What | Done when | Status |
|---|---|---|---|
| 0 | Repo, Docker Compose skeleton, `.env.example`, README, CLAUDE.md, PROGRESS.md, CI workflow | `docker compose up` shows a placeholder page and the API health check passes | Done |
| 1 | Homepage UI (3D hero, name, feature cards, URL input) + API stub | Looks right on desktop and mobile; input validates URLs and calls the stub | Done |
| 2 | Safe fetching: SSRF guard, sandbox, redirect chain, screenshot | A scan returns screenshot + redirect chain; private IPs blocked (with tests) | Done |
| 3 | Recon: RDAP, DNS, GeoIP/ASN, TLS, CT, headers | Recon panel shows real data for a test domain | Done |
| 4 | Analysis v1: lexical + content features, scam type rules, rule-based score, reasons; live progress; results page v1 | Full scan flow works end to end with plain-language reasons | Done |
| 5 | Blacklist integrations with caching and quota handling | Each service shows a result or a clear "not configured / quota reached" | Done |
| 6 | Data: dataset loaders, fingerprinting, cron feed ingestion (GitHub Actions) | Datasets loaded; feeds ingest on schedule; admin view shows ingestion health | Done locally. The schedule waits for a shared database |
| 7 | Nightly family clustering, Family Finder, 4 sibling tabs | A scanned page matches a family when a similar page exists | Done |
| 8 | SiNMULI graph module + network map | Local signed graph built, signs inferred, unknown neighbors labeled, map renders | Done |
| 9 | ML scoring (LightGBM) combined with rules; evaluation on a held-out set | Precision/recall report written to `docs/`; score uses the model | Done |
| 10 | Extras: PDF report, trends dashboard, feedback button, bulk scan, API keys for our API, rate limiting, deploy scan server to a free host | Each feature works and is documented | Done, except the deployment itself (guide written, needs Rohit's accounts) |

## Log

- **2026-09-24:** Project set up. Repo public from day one; Rohit has the Student Developer Pack; Actions will run the cron jobs.
- **2026-09-24:** Phase 0 built. `docker compose up` serves the placeholder on :3000 and `/health` reports database ok, sandbox ok, Safe Browsing key set.
- **2026-09-24:** Removed Claude co-author lines from all commits (history rewritten, force-pushed by Rohit). No attribution from now on.
- **2026-09-24:** Phase 1 built. Homepage live on GitHub Pages. Local stack scans reach the `/scan` placeholder.
- **2026-09-25:** Phase 2 built. Real scans on the local stack (http://localhost:3000). The live Pages site still shows "scanner offline" by design until a public scan server exists.
- **2026-09-25:** Homepage redesigned (OneText-inspired split hero with a live scan graph). MaxMind key added.
- **2026-09-25:** Phase 3 built. Recon adds about 3 seconds to a scan.
- **2026-09-25:** Phase 4 built. Scans give a verdict, a score, a scam type, and plain reasons; progress streams live; results are saved and reopen from a link.
- **2026-10-02:** Mentor presentation made (kept out of git). Phase 5 built: blacklist checks with a quick first answer.
- **2026-10-03:** Phase 6 built: fingerprints, the page library, the PhreshPhish loader (55,080 pages loaded locally), and feed ingestion on GitHub Actions (dry run passed).
- **2026-10-03:** Phase 7 built: 531 scam families found, Family Finder and Sibling Hunter in the scan and the report.
- **2026-10-03:** Phase 8 built: link-graph inference after SiNMULI, the network map, and the server map.
- **2026-10-03:** Phase 9 built: the page-reading model (97.5% precision, 75.9% recall on 15,558 unseen pages) is one more reason in every score. A check on real honest pages showed the first version had learned shortcuts from the dataset; the features, the training weights, and the scoring were changed so the model cannot raise a verdict alone. The same check led to four rule fixes (free-hosted sites, scam phrases on long pages, brands' own GitHub pages, the headline wording).
- **2026-10-03:** Phase 10 built: PDF report, mistake reports, bulk scan, trends, API keys, and the deployment guide. All ten phases are built. What remains needs accounts only Rohit can create (see `docs/DEPLOY.md`).

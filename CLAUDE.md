# LinkLens

Paste a suspicious link, get a safe verdict: risk score (0 to 100), scam type, scam family, sibling sites, server and owner details, and plain reasons. Tagline: *"Paste a link. See who's really behind it."*

Full original brief: `docs/PROJECT_BRIEF.md`. This file wins where they disagree. Stack reasons: `docs/TECH_DECISIONS.md`. Datasets: `docs/DATASETS.md`. Status: `PROGRESS.md`.

## Working with Rohit

- Final-year B.Tech Cybersecurity student, has the GitHub Student Developer Pack (GitHub Pro). Personal, non-commercial project, no deadline.
- Repo: https://github.com/TheBhardwajRohit/LinkLens (public from day one). Commit as `TheBhardwajRohit <149057886+TheBhardwajRohit@users.noreply.github.com>` (set in repo-local git config) so no personal email is exposed.
- **Commits and PRs carry no Claude attribution.** Never add `Co-Authored-By` trailers or "Generated with Claude" lines. Every commit must show only TheBhardwajRohit (Rohit's rule, 2026-09-24).
- Datasets: Claude picks the best ones and downloads them when needed (Rohit's OK, 2026-09-24).
- Explain in simple, plain words. Define any technical term in one line.
- Docs, UI text, commits: plain, human, concise. No filler. **No em-dashes.**
- Before each phase: short plan, wait for "go". Small steps, project runnable after each. Commit with clear messages. (On 2026-10-02 Rohit said to build all remaining phases without stopping; the "go" rule applies again to anything after phase 10.)
- After each step: update `PROGRESS.md`, explain what was done in 3 to 5 simple lines. Update this file when a decision changes.
- Log every stack choice and its reason in `docs/TECH_DECISIONS.md`. At the end, Rohit wants a clear "why this stack" answer.
- Never guess API behavior or limits. Check official docs; say when unsure. Ask before adding any paid service.
- Keys only in `.env` (gitignored) and GitHub Actions secrets. Never in code, docs, or commits. App must work with fewer signals when a key is missing.

## Where things run (decided 2026-09-24)

| Piece | Runs on | Notes |
|---|---|---|
| Website | GitHub Pages (static single-page app), live at https://thebhardwajrohit.github.io/LinkLens/ | Deployed by `.github/workflows/pages.yml`. Built with `VITE_API_URL=none` until the repo variable `VITE_API_URL` names a public scan server, so the live site makes no API calls yet. |
| Scheduled jobs (feed ingestion, nightly clustering, dataset seeding) | GitHub Actions | Public repo, so standard runner minutes are free. Ingest every 30 to 60 min. |
| Database + screenshots | Supabase free (Postgres 500 MB, storage 1 GB, 50 MB max file) | Pauses after 1 week without DB activity; the cron keeps it awake. Local Postgres in Docker for dev and tests. |
| Live scan server (API + sandbox) | Docker containers. Rohit's PC for now; free cloud host picked in phase 10 | GitHub cannot host it. Actions terms forbid using Actions as part of a serverless app. |

- Raw datasets are never stored in git or Supabase. Jobs stream them, compute fingerprints, store only fingerprints + metadata + small thumbnails.
- Git is for code only (GitHub: repo ideally under 1 GB, files over 100 MiB blocked).
- Actions schedules can be delayed or dropped at busy times (top of the hour): use odd minutes like `17 */3 * * *`.
- Public repos: scheduled workflows are disabled after 60 days with no repo activity. **No keep-alive** (decided 2026-10-02): GitHub took down the best-known keep-alive action for breaking its terms. If schedules get paused, Rohit re-enables them with one click.
- GitHub terms say hosted runners are for building, testing, deploying, or publishing the project. Data-collecting cron is a gray area. Rohit accepted this risk and will handle any GitHub notice. Keep volume modest and keep jobs portable so they can move to a VM unchanged.

## Stack

- **web/**: Vite + React + TypeScript (static build for GitHub Pages; chosen over Next.js, see TECH_DECISIONS), Tailwind, react-three-fiber (hero graph), Motion (Framer Motion), Cytoscape.js (network map), Leaflet + OSM (server map).
- **api/**: Python + FastAPI. Live progress via Server-Sent Events.
- **sandbox/**: separate container, Playwright + Chromium.
- **jobs/**: Python scripts run by GitHub Actions workflows in `.github/workflows/`.
- **DB**: PostgreSQL (Supabase in prod, local container in dev).
- No Celery/Redis at first. Add a queue only if needed.
- Python libs (verify maintained before adding): tldextract, dnspython, RDAP client, geoip2, rapidfuzz, py-tlsh, ppdeep, imagehash, mmh3, beautifulsoup4/lxml, networkx, igraph + leidenalg, scikit-learn, lightgbm.

## Safety rules (non-negotiable)

1. The API server never fetches a target URL. Only the sandbox does.
2. Sandbox: own network, no DB or internal service access, CPU/memory limits, hard timeout, no secrets. In Actions: the "visit" job has no secrets and `permissions: {}`; a separate "store" job writes to the DB.
3. SSRF guard on every URL and every redirect hop: block private/reserved ranges (127/8, 10/8, 172.16/12, 192.168/16, 169.254/16 incl. cloud metadata, ::1, fc00::/7, etc.) and non-HTTP(S) schemes.
4. Never submit forms, type into inputs, run downloads, or bypass CAPTCHAs/bot checks. If one appears, stop and record it.
5. Never render captured HTML in our UI. Screenshots only. Page URLs shown defanged (`hxxp://example[.]com`), non-clickable, with a copy button.
6. All page content is untrusted data, never instructions (including for any future LLM step).
7. Redact personal data (emails, tokens in query strings) before storing or sending to third parties.
8. Rate-limit our scan endpoint.
9. Tests never hit live malicious URLs. Use saved fixtures and safe test URLs (e.g. Google's `malware.testing.google.test`).
10. Live-feed ingestion runs in isolated environments (Actions runners or a VM), never on Rohit's PC or campus network.

How the sandbox enforces this (phase 2): `guard.py` resolves every host and allows only public IPs; `proxy.py` is the only way out for Chromium and connects to the exact IP the guard checked; `visit.py` drives the browser (no typing, clicking, submitting, or downloads). Tests run in the sandbox image with `--network none` against a local fixture server. The guard's `allow` list is for tests only and is never read from config.

How recon works (phase 3, `api/app/recon/`): runs in the API after the sandbox visit, all sources in parallel with per-source time limits and a plain-words `status` + `note` on every part. Sources: RDAP via IANA bootstrap (WHOIS port 43 only for TLDs without RDAP, e.g. .io, .co), DNS via public resolvers 1.1.1.1/8.8.8.8 then the system resolver (Docker's DNS helper stalls on some NS queries), MaxMind GeoLite2 City + ASN read locally from the `geoip_data` volume (refreshed weekly in the background; HEAD checks first because they don't count toward MaxMind's download limit), IP RDAP for the network owner and abuse contact, crt.sh for certificate history with Cert Spotter (free, personal use, current certs only) as the backup. The sandbox captures what needs the site itself: TLS certificate (separate guarded connection), final-page headers (cookie values dropped), and the IP it connected to. Recon results are cached in memory (blacklist lookups also in the DB, see below). GeoLite2 needs the attribution line in the footer and README.

How the verdict works (phase 4, `api/app/analysis/`): `lexical.py` (link clues, lookalikes against `data/brands.json`), `content.py` (page clues from the HTML, server side only), `scamtype.py` (rule scores per scam type, needs 3+ points of evidence), `score.py` (every rule is a plain-words `Reason` with points; good signs are negative; clamp 0 to 100). A plain brand mention is not impersonation: it counts only via a lookalike link, the page title, or a mention plus a sensitive field. Popular sites (Tranco top 100k, `toplist.py`, refreshed monthly into the `lists_data` volume) are never flagged as lookalikes; free-hosting sites are judged one by one via private suffixes. Blocked private-address links are at least Suspicious. Summaries say "looks like" / "likely", never "confirmed".

How scans flow (phase 4): `POST /scans` returns an id at once and runs `pipeline.run_scan` in the background; `GET /scans/{id}/events` streams steps as SSE from the in-memory job (`jobs.py`, kept 15 min); `GET /scans/{id}` reopens a result, always redacted (`redact.py` strips emails, tokens, session IDs from links); `POST /scan` is the same pipeline in one reply (CI, scripts). Every scan is saved in Postgres (`storage.py`, table `scans`, screenshot in its own column); a failed save never loses the live result. Scans are rate-limited per client IP (`SCAN_RATE_LIMIT_PER_HOUR`, default 20). The website follows the stream, falls back to polling, and pushes `?scan=<id>` so results can be reopened or shared.

How blacklists work (phase 5, `api/app/blacklists/`): every source runs in parallel with a 7 second limit and always ends with a plain status (`listed`, `clean`, `unknown`, `info`, `not_configured`, `quota`, `timeout`, `error`, `skipped`). Sources: Google Safe Browsing Lookup v4 (key in the `x-goog-api-key` header), Phishing.Database lists (downloaded to the `lists_data` volume every 6 hours, kept in memory as sorted 8-byte hashes, checked locally), VirusTotal v3 (lookups only, 4 a minute), URLhaus (needs the abuse.ch key), urlscan.io search (no key needed; history only, since verdict search needs an account), and LinkLens's own earlier scans. Blacklists run first on the pasted link (quick answer), then again during recon for the final page and the stops in between. Links are redacted before they leave the server; private-address stops are never sent. Results are cached in memory and in the `lookup_cache` table (`api/app/cache.py`). Wording follows Google's rules: "lists this link as suspected ...", plus "Advisory provided by Google" and Google's notice in the report. Tests swap `blacklists.http.transport` for a fake; `conftest.py` stubs `blacklists.check` everywhere else.

How fingerprints and the page library work (phase 6): `api/app/fingerprint.py` takes TLSH of the HTML, an exact hash and a 64-bit simhash of the tag sequence, a simhash of the visible words, pHash of the screenshot (blank screenshots get none), and the Shodan-style MurmurHash3 of the favicon (the sandbox loads the icon in a second tab, through the proxy; the API only hashes it). `api/app/pages.py` owns the `pages` table (one row of fingerprints per page from scans, feeds, or datasets; raw HTML never stored), plus `families`, `ingest_runs`, and `feed_urls`. Each 64-bit hash is cut into four 16-bit pieces kept in `pages.bands` (GIN index) for fast candidate search. `api/app/library.py` `digest_page(url, html)` is the one call jobs use to read a page; `api/app/ml/features.py` is the model's feature list (link and page only, no popularity). `GET /stats` feeds the "What LinkLens knows" section.

How the data jobs work (phase 6, `jobs/`, details in `jobs/README.md`): `seed_phreshphish.py` streams PhreshPhish rows, stores fingerprints, and writes `/data/ml/phreshphish-<split>.parquet` (the `ml_data` volume) for training. `ingest.py` has three steps: `plan` (feeds, dedupe via `feed_urls`), `visit` (sandbox, no secrets, fingerprints the page itself so raw HTML never leaves the job), `store` (recon + database). Workflows: `ingest.yml` (hourly at minute 17, skipped unless the repo variable `INGEST_ENABLED` is `true`; manual runs can be dry runs), `seed.yml` (manual). Run jobs locally with `docker compose run --rm jobs python -m jobs.<name>` (compose profile `jobs`). Local page library: 40,000 train + 16,000 test PhreshPhish rows loaded on 2026-10-02.

How families and siblings work (phase 7): `api/app/similarity.py` scores how alike two pages are: each kind of fingerprint that agrees adds points (code, structure, words, look, icon), and a match needs 3 points from at least 2 kinds. `jobs/cluster.py` (nightly, `cluster.yml`) links matching pages, takes connected components, and keeps a group as a scam family when it has 3+ pages on 2+ sites and is mostly known scam pages; a family's id is its oldest page's id, its name comes from the brand most of its pages target (`display_brand` tidies dataset names). `api/app/family.py` compares a scanned page with the library (one indexed query for candidates, then the same `compare`), ignoring pages on the scanned site itself; statuses: `matched`, `similar`, `copy` (near copy of an ordinary site's page), `none`, `skipped`, `unavailable`. `api/app/siblings.py` returns four tabs: same server (library + urlscan.io IP search; shared networks like Cloudflare are named and earn no points), same owner (certificate names, registrant, registrar + name servers + date), same design (from family matches), lookalike names (variations resolved in DNS, never visited). `GET /pages/{id}/thumb` serves our own thumbnails.

How the link graph works (phase 8, `api/app/graph.py`): SiNMULI's Algorithm 2 (arXiv:2608.19190, readable at arxiv.org/html/2608.19190v1) on the scanned site's neighbourhood. Nodes are sites; edges are hyperlinks from `pages.out_domains`; an edge's sign comes from its source (+1 known honest, -1 known scam or pointing at one, 0 unknown). Triangles with exactly one unknown edge and one unlabeled site get the sign that makes the product +1; the scanned site is then labelled by its incoming links with the 51% rule, or abstains. Site labels come from the library, the phishing lists, the brand list, and Tranco. Website: `NetworkMap` + lazy `NetworkCanvas` (Cytoscape.js), `ServerMap` + lazy `ServerMapCanvas` (Leaflet, OpenStreetMap tiles, only after a click).

How the model works (phase 9): `api/app/ml/features.py` turns the link and page into 78 numbers. Three things are left out on purpose because the dataset would teach a false shortcut from each: popularity, the query string (plus the whole link's length), and "is on free hosting" (the dataset has next to no honest examples of the last two). `jobs/train.py` trains LightGBM on the PhreshPhish feature files, weighting honest pages up in groups (page size x bare address) where scam pages outnumber them, tests on the dataset's own test split, and writes `api/app/ml/model.json` (trees as flat lists, committed) and `docs/MODEL_REPORT.md`. `api/app/ml/model.py` walks the trees in plain Python (no LightGBM in the API), rounds inputs to 32-bit like the training data, and credits each feature with its share of the answer (Saabas method) so the reason can say "mostly because of ...". `model_say` in `api/app/analysis/score.py` decides the points: +50 at 95% and up, down to -20 at 5% and under, but at most +20 and never past Safe unless the backing is 8 or more, at most +20 on a free hosting service even when backed, and never a plus on a brand's real site or a top-10,000 site. Backing = what the rules alone scored, minus signs honest and scam sites share (the free-hosting reason, marked `backs_model=False`). `Analysis` carries `rule_score` and `backing`. The model speaks only when a real page was captured (not on a bot-check screen, `is_bot_screen`). `jobs/honest_check.py` scans the honest pages in `jobs/data/honest_sites.txt` through the local scan server and saves what the model reads (`ml_data` volume); training reports on them every time. After any change to the features or to the rules: rebuild the jobs image, reload both splits (about 30 minutes), retrain, and the test `test_the_shipped_model_fits_the_feature_list` passes again. API tests run on the rules alone (the `rules_only` fixture) unless marked `real_model`. Last trained 2026-10-03: ROC AUC 0.9743, precision 97.5% and recall 75.9% at 50% on 15,558 unseen pages; 13 of 126 real honest pages rated 60%+ by the model alone, 1 above Safe in a scan.

Rule fixes made in phase 9 (found by the real-site check): a site on a free hosting service (`final.free_hosting`) is not judged by the service's domain: no domain-age or certificate-history reasons (`domain_reasons(shared_host=True)`), no same-owner siblings, and its server counts as shared. Phrase rules (`PHRASE_REASONS`) score nothing on pages of `LONG_PAGE_WORDS` (600) or more. `brands.json` lists `<name>.github.io` as official for 16 brands whose GitHub organisation is verified (checked with GitHub's API; re-check before adding more).Good signs never make a blacklisted link Safe: a listing worth 60+ points makes the verdict at least Dangerous, one worth 30+ at least Suspicious (`STRONG_LISTING`, `LISTING`). A Safe headline says "only small warning signs" when reasons are listed.

How the extras work (phase 10): `api/app/extras.py` has `POST /scans/{id}/feedback`, `GET /scans/{id}/status`, `GET /trends`, `POST /scans/bulk` (up to 10, run one after another by `pipeline.run_job`). `api/app/access.py` decides who may scan: per-address limits, or an `X-API-Key` (keys made with `python -m app.access create`, stored as SHA-256 hashes in `api_keys`), `REQUIRE_API_KEY`, and `TRUST_FORWARDED_FOR` for running behind a proxy. The PDF is the browser's print of the report (`ReportActions.tsx`, print rules in `index.css`); a server-side renderer was rejected because the only browser we have is the sandbox, which must never load internal pages. Screenshots older than 90 days are dropped at startup and nightly. `docs/DEPLOY.md` is the guide for Supabase, the hourly jobs, Azure Container Apps, and pointing Pages at the scan server (`VITE_API_URL` repo variable).

## Scan pipeline (target: blacklist verdict in seconds, full result in about 1 minute)

1. Normalize: add scheme, decode punycode/IDN (show both, flag lookalikes), expand shorteners, redact personal data.
2. SSRF guard.
3. Blacklists in parallel, cached: Safe Browsing, VirusTotal, URLhaus, urlscan search, own DB.
4. Sandbox visit: redirect chain (3xx, meta, JS), final URL, screenshot, HTML, favicon, contacted domains, forms, scripts, iframes.
5. Recon: RDAP/WHOIS, DNS (A, AAAA, MX, NS, TXT, CNAME), GeoIP/ASN/host/abuse contact, TLS cert, crt.sh, reverse IP, headers/tech stack.
6. Lexical: length, entropy, subdomain depth, digit ratio, `@` `//` `-`, IP host, odd TLD, keywords (login, verify, kyc...), shortener, edit distance to brands.
7. Content: asks for password/card/CVV/OTP/UPI PIN/Aadhaar/PAN, form posts to other domain (SFH), brands, crypto wallets, base64 density, iframes, right-click block, link ratios, `mailto:`. Decides scam type.
8. Fingerprint: TLSH/ssdeep (HTML), DOM tag-sequence hash, pHash (screenshot), MurmurHash3 (favicon), TF-IDF (text).
9. Siblings: same server, same owner, same design, lookalike names.
10. SiNMULI graph inference.
11. Score: plain rules, then the model's opinion as one more reason (limited, see "How the model works"). 0 to 30 Safe, 31 to 69 Suspicious, 70 to 100 Dangerous. Plain reasons.
12. Save everything.

Scam types: banking/financial fraud, credential phishing, crypto, fake prize/advance-fee, fake shop, tech support, malware download, job/task scam, government impersonation (e-challan, tax refund). Include Indian brands and patterns (SBI, HDFC, ICICI, India Post, UPI, KYC).

## Results page order

Verdict card, screenshot, scam type tag, family card, siblings (4 tabs), network map, server/recon + map pin, link trail, "why we flagged it", blacklist results, actions (PDF, report mistake, share, scan another).

## Homepage

Redesigned 2026-09-25, inspired by OneText's split hero (Rohit approved). Replaces the brief's original layout.

- Slim top bar: logo, Features, How it stays safe, GitHub, "Scan a link".
- Hero 60/40. Left: "See who's really behind the link.", subheading, glass input with blue Scan button, trust line with scanner status. Right: 3D force graph (`web/src/graph/`). Before a scan it plays a looping example story in speech bubbles (labeled "Example scan", reserved `.example` names only); during a scan it pulses; after, it draws the real scan (chain, loaded domains, blocked hosts in red).
- Dark panel overlapping the hero bottom: safety quote + 4 tiles. Then the scan report (after a scan), then the feature grid.
- Report order (built): verdict, safe preview, scam family, sibling sites (4 tabs), network map, who's behind it + server map, link trail, why we flagged it, blacklist results.
- Feature cards: glass, hover glow, Live / Coming soon badges. Flip `status` in `web/src/features.ts` when a phase ships. Never claim a check that doesn't exist.
- Blue is the action color. Green, yellow, and red mean verdicts only (red also marks blocked hosts in the graph).
- No full-page 3D background. Phones stack text first. Reduced motion renders a still graph; no WebGL, a crash, or under 24 fps falls back to a flat SVG graph.
- Fonts: Red Hat Display (headings), Red Hat Text (body), self-hosted.
- To see 3D visually when the browser pane is hidden (it pauses animation frames), screenshot the local web container with Playwright from the sandbox test image.

## Family data

- Seed datasets (see `docs/DATASETS.md`): PhreshPhish first, then Phishpedia and Zenodo screenshot sets, Tranco for benign/brand lists.
- Feed ingestion cron: new URLs from free feeds, dedupe, sandbox fast (scam pages die in hours), store fingerprints + recon.
- Nightly clustering: link pages with close TLSH, close pHash, same favicon hash, same DOM hash. Connected components first; Leiden/HDBSCAN later. Label families by top target brand.
- Full screenshots kept 60 to 90 days, then thumbnail + fingerprints only.

## Data sources and keys

- Configured: Google Safe Browsing (non-commercial Lookup API; key tested OK 2026-09-24).
- Configured: MaxMind GeoLite2 (account ID + license key in `.env`; download auth checked OK with HEAD requests 2026-09-25, which don't count toward the daily limit).
- Not yet (code is ready, shows "not set up"): VirusTotal, abuse.ch (URLhaus). urlscan.io search works without a key; a key would add verdicts.
- Phishing.Database lists (MIT license, https://phish.co.za/latest/) need no key.
- Feeds: Phishing.Database (default), URLhaus (needs the abuse.ch key). OpenPhish community is supported but off by default: its terms (read 2026-10-02) forbid passing the data or anything made from it to third parties, which a public site would do. No OpenPhish academic access (Rohit's choice). **Never use PhishTank** (registration closed).

## SiNMULI (phase 8)

Node = registered domain (tldextract). Edge = external hyperlink, signed by source label (+1 benign, -1 malicious, 0 unknown). Keep triads with exactly one unlabeled node and one unknown edge. Infer sign so `s(i,j)*s(j,k)*s(i,k) = +1`, fall back to weak balance. Label node if >51% of incoming edges agree, else abstain. Add centrality features. Only use the local ego graph (radius 1 to 2). New domains have few links, so say so in the UI. Paper is newer than Claude's training data; ask Rohit for the PDF when needed.

## Honest limits (show in UI)

Family Finder starts weak. Graph weak for new domains. Say "likely"/"matches", not "confirmed", unless a blacklist confirms. Low free quotas, so degrade gracefully. Some scans will be partial (bot blocks, geo-fencing, dead pages); say so clearly.

## Phases

0 skeleton, 1 homepage, 2 safe fetching, 3 recon, 4 analysis v1 + results page, 5 blacklists, 6 datasets + fingerprints + ingestion, 7 families + siblings, 8 SiNMULI + map, 9 ML scoring, 10 extras. All built as of 2026-10-03. Still open, and only Rohit can do them: Supabase project, switching on the hourly jobs, deploying the scan server (`docs/DEPLOY.md`), optional VirusTotal / abuse.ch / urlscan keys. Details in `PROGRESS.md`.

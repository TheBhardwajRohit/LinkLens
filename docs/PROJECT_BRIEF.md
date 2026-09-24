> **Note (2026-09-24):** This is the original planning brief, kept as the full reference.
> Some decisions changed after it was written (hosting, storage, data sources, job runner).
> `CLAUDE.md` and `docs/TECH_DECISIONS.md` hold the current decisions. When they disagree with this file, they win.

# LinkLens: Project Brief for Claude Code

You are joining this project with zero prior context. This file contains everything decided so far. Read all of it before doing anything. Section 16 tells you what to do first.

---

## 1. Who you're working with

- **Rohit**, final-year B.Tech Cybersecurity student. Knows security well (CTFs, recon tools), but wants explanations in simple, plain words. If you use a technical term, explain it in one line.
- This is an **academic / portfolio project, non-commercial**. That matters, because several free data sources we plan to use are for non-commercial use only.
- **Writing style** for docs, UI text, and commit messages: plain, human, concise. No filler phrases. No em-dashes.

---

## 2. How we got here (background)

Before this session, Rohit and Claude (in the Claude chat app) planned the project together:

1. Rohit shared a research paper, **SiNMULI** (signed-network approach to malicious URL identification, arXiv:2608.19190). We pulled out the parts useful for this project (section 7).
2. We defined the features, the homepage, the scan pipeline, and the results page (sections 3 to 5).
3. We worked out where the "family" data comes from, since Rohit won't be scanning links manually (section 6).

Nothing has been built yet. You are starting from an empty folder.

---

## 3. What we're building

A modern website where someone pastes a suspicious or malicious link. Behind the scenes, the system safely analyzes it and tells the user:

- Is it dangerous? (score out of 100)
- Which scam **family** does it belong to?
- Which other websites are its **siblings**?
- What **type of scam** is it? (financial fraud, crypto scam, fake login, etc.)
- Where is the **server**, who hosts it, who registered the domain?
- **Why** was it flagged?

**Working name: LinkLens** (placeholder; alternatives: TraceLink, ScamScope, PhishMap).

### Homepage

- **Dark theme.** A full-screen 3D background of glowing dots connected by thin lines, arranged in several depth layers (a "web of links"). It drifts slowly and shifts slightly with mouse movement (parallax), giving a real sense of depth. Most dots are blue/cyan, a few are red, hinting at scam sites hidden among normal ones.
- **Order on the page:** name first, then feature list, then the URL input.
  - Big centered **name**, tagline under it: *"Paste a link. See who's really behind it."*
  - **Feature cards** floating at different depths, tilting slightly on hover.
  - **URL input** with a "Scan" button.
  - Optional: a "Scan a link" button in the hero that scrolls down to the input.
- Must work well on mobile. Respect `prefers-reduced-motion`. Fall back to a static gradient on weak devices.

**Feature cards (one line each):**

| Feature | One-liner |
|---|---|
| Instant Verdict | Safe, Suspicious, or Dangerous, with a score out of 100 |
| Family Finder | Which scam group or scam template this link belongs to |
| Sibling Hunter | Other websites run by the same people |
| Scam Type | Financial fraud, fake login, crypto scam, fake prize, and more |
| Server Tracker | Server location, hosting company, and who registered it |
| Link Trail | Every jump the link makes before the final page |
| Safe Preview | A screenshot, so you never open the page yourself |
| Why It's Flagged | Plain reasons, not just a number |
| Network Map | A clickable map of the link and its connections |
| Download Report | Everything saved as a PDF |

---

## 4. What happens after the user clicks Scan

While this runs, the user sees a **live progress screen** where each step ticks off as it finishes (use Server-Sent Events or WebSockets). Targets to aim for: a quick first verdict from blacklists in a few seconds, full results within about a minute.

1. **Normalize the link.** Add a missing scheme, decode punycode/IDN (show both forms, flag lookalike characters), expand shorteners. Redact personal data (emails, tokens in query strings) before storing it or sending it to any third party.
2. **SSRF guard.** Resolve DNS and block private/reserved ranges (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16 including cloud metadata, ::1, fc00::/7, etc.) and non-HTTP(S) schemes. **Re-check on every redirect hop.**
3. **Quick blacklist checks** (in parallel, cached): Google Safe Browsing, VirusTotal, URLhaus, urlscan.io search, and our own database.
4. **Sandbox visit.** Headless Chromium (Playwright) in an isolated container. Record: full redirect chain (HTTP 3xx, meta refresh, JS redirects), final URL, screenshot, HTML, favicon, every domain the page contacts, forms (action URLs, input types), scripts, iframes. Hard timeout. Never execute downloads. **Never submit forms or type anything.** If a CAPTCHA or bot check appears, stop and record it; do not try to bypass it.
5. **Recon.**
   - RDAP/WHOIS: registrar, creation date (domain age), expiry, registrant if public
   - DNS: A, AAAA, MX, NS, TXT, CNAME
   - IP to GeoIP (country, city, coordinates), ASN, hosting provider, abuse contact
   - TLS certificate: issuer, validity, SANs
   - Certificate Transparency history (crt.sh): other domains on the same certificate
   - Reverse IP (other domains on the same IP) where a source is available
   - HTTP headers and tech-stack fingerprint
6. **Read the link itself (lexical features).** Length, Shannon entropy, subdomain depth, digit ratio, special characters (`@`, `//`, `-`), IP as host, unusual TLD, keyword tokens (login, verify, update, secure, kyc), shortener use, and edit distance to known brand domains (typosquats like `paypa1.com`).
7. **Read the page (content features).** Does it ask for a password, card number, CVV, OTP, UPI PIN, Aadhaar or PAN? Does the form send data to a different domain than the page (SFH mismatch)? Brand logos or brand names? Crypto wallet addresses? Base64 density, iframes, right-click disabled, internal vs external link ratio, `mailto:` anchors. This decides the **scam type**.
8. **Fingerprint the page.** TLSH (and/or ssdeep) of the HTML, a DOM-structure hash (tag sequence), perceptual hash (pHash) of the screenshot, MurmurHash3 of the favicon, TF-IDF vector of the page text. Compare against stored families.
9. **Find siblings** (4 separate kinds, see section 5).
10. **Graph inference** using the SiNMULI method (section 7).
11. **Final score.** Combine everything into a 0 to 100 risk score, a verdict, and a list of plain-language reasons. Start with a rule-based score; add an ML model later (phase 9). Initial thresholds: 0 to 30 Safe, 31 to 69 Suspicious, 70 to 100 Dangerous (tune later).
12. **Save everything.** Every scan becomes part of the database.

### Scam type categories (starting set)

Financial / banking fraud, credential phishing (generic login), crypto scam, fake prize / lottery / advance-fee, fake shopping site, tech support scam, malware download, job / task scam, government impersonation (fake e-challan, tax refund, etc.). Include India-relevant brands and patterns (SBI, HDFC, ICICI, India Post, UPI, KYC update scams) alongside global ones.

---

## 5. Results page (top to bottom)

1. **Verdict card:** colored badge (green / yellow / red), score, one-line summary like *"This is a fake bank login page."*
2. **Safe screenshot** of the page.
3. **Scam type tag**, e.g. *Financial Fraud, Banking*.
4. **Family card**, e.g. *"Matches Family #12: fake SBI login, 43 other pages, first seen 3 Sept."*
5. **Siblings**, in 4 tabs:
   - Same server (shared IP / ASN / hosting)
   - Same owner (shared registrant, nameservers, certificate)
   - Same design (same kit fingerprint)
   - Lookalike names (typosquat permutations that resolve)
6. **Network map:** interactive graph (click, drag, zoom). Red = bad, green = safe, grey = unknown.
7. **Server and recon details:** world map pin, country, city, hosting company, IP, domain age, registrar, certificate info.
8. **Link trail:** redirect chain shown as a simple chain of hops.
9. **Why we flagged it:** plain checklist, e.g. "Domain is only 3 days old", "Asks for card number and CVV", "Looks 94% like a known scam page", "Shares a server with 12 known scam sites".
10. **Blacklist results:** what each external service said.
11. **Actions:** Download report, Report a mistake, Share result, Scan another link.

**Security rules for this page:** never render captured HTML directly (XSS risk). Show the screenshot only. Show URLs from the page as non-clickable, defanged text (`hxxp://example[.]com`) with a copy button.

---

## 6. Where the family data comes from

Rohit won't be scanning links manually, so the database must fill itself. Three sources:

### a) Datasets (head start on day one)

Load known scam pages, run the fingerprinting from step 8 on them, and store the results.

- **Phishpedia dataset** (USENIX Security '21): about 30k phishing sites, each with URL, HTML, screenshot, and target brand. https://github.com/lindsey98/Phishpedia
- **Zenodo Phishing Website Dataset**: about 10k sites (phishing and legitimate), 86 target brands, with screenshots, HTML, WHOIS, IP, and SSL info. https://zenodo.org/records/8041387
- **Ariyadasa et al. Phishing Websites Dataset** (the SiNMULI paper's seed data): doi:10.17632/n96ncsr5g4.1
- **Phish360** (multimodal: URL, HTML, screenshots): https://web.cs.hacettepe.edu.tr/~selman/phish360-dataset/
- For known-good domains (benign labels, brand list for typosquat checks): a top-sites ranking such as the Tranco list.

Check each dataset's license before use. Note these pages are a few years old: good for learning what families look like, not for current campaigns.

### b) Cron job: feed ingestion (every 30 to 60 minutes)

1. Download the newest URLs from free phishing/malware feeds (section 9)
2. Drop ones already seen
3. Send new ones through the sandbox immediately (scam pages often die within hours, so speed matters)
4. Store screenshot, HTML, favicon, fingerprints, recon data

### c) Nightly clustering job

Once a night, group all stored pages into families automatically. Nobody names families by hand.

- Link two pages if they are strongly similar (close TLSH distance on HTML, small pHash distance on screenshot, identical favicon hash, same DOM-structure hash).
- Start simple: connected components on that similarity graph. Upgrade to Leiden/Louvain or HDBSCAN later if needed.
- Label each family by its most common target brand: "Family #12: fake SBI login, 40 pages, first seen 3 Sept."
- At scan time, only compare the new page against these precomputed families (fast).

### Also

- **urlscan.io search:** query its public scan history for pages sharing the same IP, domain, or hash. Extra source, not the main one (low free quota).
- **User scans** feed back into the database.
- **Storage:** keep full screenshots for a limited window (e.g. 60 to 90 days), then keep only fingerprints and a small thumbnail.

---

## 7. Research paper: SiNMULI (what to reuse)

**Paper:** "SiNMULI: Novel Signed Network Approach for Malicious URL Identification", Gayen, Mondal, Jana (IIIT Guwahati), arXiv:2608.19190. Code and data (per the paper): https://github.com/sayanmondal2098/SinMuli. Check its license before reusing any code. If you need details beyond this summary, ask Rohit for the PDF.

### Core idea in plain words

Websites link to each other. Model this as a graph: each domain is a node, each external hyperlink is a directed edge. Sign each edge by its source: **+1 if the source is known benign, -1 if known malicious, 0 (unknown) if the source is unlabeled**. Then infer unknown edge signs from their neighbors, and label unknown domains by majority vote. "Tell me who your friends are and I'll tell you who you are," done with math.

### Mechanics to implement

1. **Node = registered domain** (use tldextract; all subdomains of a site collapse into one node).
2. **Edges = external hyperlinks** found on crawled pages (one-hop crawl from the seed page).
3. **Triad filtering:** only keep triads with **exactly one unlabeled node and exactly one unknown edge**.
4. **Sign inference (directed balance):** for a triad with known signs s(i,j) and s(j,k), infer s(i,k) so that `s(i,j) * s(j,k) * s(i,k) = +1` (strong balance). If that conflicts with existing labels, fall back to weak balance. Prefer the source node's own label if known.
5. **Node labeling (51% rule):** for an unlabeled node, count incoming positive and negative edges. Positive share > 0.51 = benign; negative share > 0.51 = malicious; otherwise unknown (tie policy: abstain).
6. **Centrality features:** the paper found malicious nodes have lower eigenvector centrality, lower in/out-degree, and sit on the edges of communities. Compute these (NetworkX) and feed them into the risk score as features.
7. **Feature checklist (paper's Table 6):** lexical URL structure, host tricks (IP host, shorteners, `@`), semantic tokens, document size and inlined/base64 assets, forms and password fields, SFH domain mismatch, scripts and UI tricks (pop-ups, right-click disable), iframes, internal vs external link ratio, empty and `mailto:` anchors, external resource dependence. Most of this overlaps with steps 6 and 7 in section 4.

### Caveats (important)

- Full triad enumeration is expensive (worst case O(|E|^3)). **Only enumerate triads in the local neighborhood** (ego graph, radius 1 to 2) around the scanned domain.
- **Brand-new phishing domains usually have almost no inbound links**, so graph inference often has nothing to work with. The paper admits this. Recon, content, and fingerprint signals must carry the verdict when the graph is too thin, and the UI should say so.
- The paper reports very high accuracy (around 99.9%), but on its own crawled graph, and some reported numbers are inconsistent across its sections. Treat it as a promising method, not a benchmark to quote.

---

## 8. Techniques ("the math"), at a glance

| Technique | Used for |
|---|---|
| Signed graph + directed balance theory + 51% vote | Labeling unknown domains from their neighbors (SiNMULI) |
| Graph centrality (eigenvector, PageRank, degree, clustering) | Risk score features |
| Louvain / Leiden community detection | Grouping infrastructure into campaigns |
| Shannon entropy | Spotting random-looking (auto-generated) domains |
| Levenshtein / Damerau-Levenshtein distance | Typosquat detection |
| TLSH / ssdeep fuzzy hashing | Same scam kit, slightly modified HTML |
| pHash (perceptual hash) | Visually identical pages |
| MurmurHash3 favicon hash | Same kit (authors rarely change the favicon) |
| TF-IDF + cosine similarity | Similar page text |
| Gradient boosting (LightGBM / XGBoost) | Combining all signals into one score (phase 9) |

---

## 9. External services

**Verify current terms, quotas, and API details from official docs before building on any of these.** Notes below were checked in September 2026 but may change.

| Service | Use | Notes |
|---|---|---|
| OpenPhish community feed | Phishing URLs for ingestion | Free, updated every 12 hours, non-commercial use only |
| OpenPhish premium (academic) | Better ingestion | Offered free to academic institutions for research. Rohit may request it through his university. Updates every 5 minutes, includes targeted brand, IP, ASN, GeoIP, sector |
| URLhaus (abuse.ch) | Malware URLs, lookups | Free Auth-Key required (all abuse.ch APIs need it); hourly and daily feeds |
| Phishing.Database | Phishing domains/links | Free, updated every few hours |
| Google Safe Browsing Lookup API | Blacklist check | Non-commercial only (Web Risk API is the commercial version) |
| VirusTotal public API | Blacklist check | Very low free quota; cache aggressively, lookups only |
| urlscan.io | History search, optional scans | Search before scanning (search doesn't spend scan quota). Low free quotas. Submit as unlisted/private if the URL may contain personal data. Don't mirror their dataset |
| MaxMind GeoLite2 (City + ASN) | GeoIP and ASN | Free account, local database, no per-request limits |
| crt.sh | Certificate Transparency history | Free; can be slow, add timeouts and caching |
| RDAP | Domain registration data | Prefer over raw WHOIS where available |
| **PhishTank** | **Do not use** | New user registration has been closed since 2020 and was still closed as of June 2026 |

All API keys go in `.env` (gitignored). Provide `.env.example`. The app must still work (with fewer signals) when a key is missing.

---

## 10. Safety rules (non-negotiable)

1. **The API server never fetches a target URL itself.** Only the sandbox does.
2. The **sandbox container** has its own network, no access to the database, Redis, or other internal services, CPU/memory limits, a hard timeout, and no stored secrets.
3. **SSRF guard** on every URL and every redirect hop (section 4, step 2).
4. **Never submit forms, type into inputs, or bypass CAPTCHAs/bot checks.**
5. **Never render captured HTML in our UI.** Screenshots only; defanged, non-clickable URLs.
6. Treat all page content as untrusted data. If an LLM is ever added to the pipeline, page text is untrusted input, never instructions.
7. Redact personal data from submitted URLs before storing or sharing with third parties.
8. Rate-limit our own scan endpoint to prevent abuse.
9. Tests must not hit live malicious URLs. Use saved fixtures (HTML, screenshots) and safe test URLs.
10. During development, run live-feed ingestion on a cloud VM or isolated environment, not directly on Rohit's personal machine or campus network.

---

## 11. Suggested tech stack (confirm with Rohit before starting)

- **Frontend:** Next.js (TypeScript), Tailwind CSS, react-three-fiber / Three.js for the 3D hero, Framer Motion for animation, Cytoscape.js for the network map, Leaflet + OpenStreetMap tiles for the server map.
- **Backend API:** Python + FastAPI (Python has the best security and analysis libraries).
- **Background jobs:** Celery (or RQ/arq) with Redis. Scheduled jobs via Celery beat or APScheduler.
- **Sandbox:** separate Docker container with Playwright + Chromium.
- **Database:** PostgreSQL. Screenshots on a local volume first; S3/MinIO later if needed.
- **Python libraries (verify each is maintained):** tldextract, dnspython, an RDAP client, geoip2, rapidfuzz, py-tlsh, ssdeep binding (e.g. ppdeep), imagehash, mmh3, beautifulsoup4 / lxml, networkx, igraph + leidenalg, scikit-learn, lightgbm.
- **Live progress:** Server-Sent Events.
- **PDF report:** render the report page to PDF with Playwright.
- **Everything runs via Docker Compose** (web, api, worker, scheduler, sandbox, db, redis).

---

## 12. Build plan (phases)

Each phase ends in a working state. Don't start the next phase until Rohit says go.

| Phase | What | Done when |
|---|---|---|
| 0 | Repo, Docker Compose skeleton, `.env.example`, README, CLAUDE.md, PROGRESS.md | `docker compose up` shows a placeholder page and an API health check passes |
| 1 | Homepage UI (3D hero, name, feature cards, URL input) + API stub | Looks right on desktop and mobile; input validates URLs and calls the stub |
| 2 | Safe fetching: SSRF guard, sandbox, redirect chain, screenshot | A scan returns screenshot + redirect chain; private IPs blocked (with tests) |
| 3 | Recon: RDAP, DNS, GeoIP/ASN, TLS, CT, headers | Recon panel shows real data for a test domain |
| 4 | Analysis v1: lexical + content features, scam type rules, rule-based score, reasons; live progress; results page v1 | Full scan flow works end to end with plain-language reasons |
| 5 | Blacklist integrations with caching and quota handling | Each service shows a result or a clear "not configured / quota reached" |
| 6 | Data: dataset loaders, fingerprinting, cron feed ingestion | Datasets loaded; feeds ingest on schedule; admin view shows ingestion health |
| 7 | Nightly family clustering, Family Finder, 4 sibling tabs | A scanned page matches a family when a similar page exists |
| 8 | SiNMULI graph module + network map | Local signed graph built, signs inferred, unknown neighbors labeled, map renders |
| 9 | ML scoring (LightGBM) combined with rules; evaluation on a held-out set | Precision/recall report written to `docs/`; score uses the model |
| 10 | Extras: PDF report, trends dashboard, feedback button, bulk scan, API keys for our API, rate limiting | Each feature works and is documented |

---

## 13. Honest limitations (keep in mind, and show in the UI where relevant)

- Family Finder starts weak and gets better as the database grows.
- Graph inference is weak for brand-new domains with few links.
- Results are probabilistic. UI copy should say "likely" or "matches", not "confirmed", unless a blacklist confirms it.
- Free API quotas are low; features must degrade gracefully.
- Some scam pages block bots, geo-fence, or die fast, so some scans will be partial. Say so clearly instead of failing silently.

---

## 14. Open questions to ask Rohit

1. Final name, or keep "LinkLens" for now?
2. Dev machine OS, and where it will be hosted later (VPS, cloud credits, demo-only)?
3. Which API keys does he have or plan to get (Safe Browsing, VirusTotal, urlscan, abuse.ch, MaxMind)?
4. Will he request OpenPhish academic access through his university?
5. Is the suggested stack (section 11) okay?
6. Public deployment or demo-only? (Affects abuse protection and costs.)
7. Any deadline (final-year project submission, competition)?

---

## 15. How to work with Rohit

- Before each phase, give a short plan in plain words and wait for approval.
- Work in small steps. Keep the project runnable after each step. Commit with clear messages.
- Update `PROGRESS.md` after each step. Update `CLAUDE.md` when a decision changes.
- At the end of each step, explain what you did in 3 to 5 simple lines.
- Don't guess API behavior or limits. Check the docs, and say when something is uncertain.
- Ask before adding any paid service.
- Keys only in `.env`, never in code or commits.

---

## 16. Your first steps

1. Read this entire file.
2. Reply with a short summary (about 10 bullets, simple words) of what you understood.
3. Check the environment: OS, git, Docker, Docker Compose, Node, Python. Report anything missing.
4. Ask the open questions from section 14 in one short list.
5. After Rohit answers:
   - Create `CLAUDE.md`: a condensed version of this brief (under about 150 lines) so future sessions load the context automatically. Keep this file as the full reference at `docs/PROJECT_BRIEF.md`.
   - Create `PROGRESS.md` with the phase checklist from section 12.
   - Create `.env.example`.
   - Propose the Phase 0 plan and wait for "go".

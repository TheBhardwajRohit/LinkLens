# LinkLens

**Paste a link. See who's really behind it.**

LinkLens checks a suspicious link safely and tells you:

- how dangerous it is (a score out of 100)
- what kind of scam it is (fake bank login, crypto scam, fake prize, and more)
- which scam family it belongs to, and which other sites are run by the same people
- where the server is, who hosts it, and who registered the domain
- why it was flagged, in plain words

You never open the page yourself. A locked-down sandbox browser visits it and takes a screenshot.

> **Status:** all ten planned phases are built. Scans run on a local install (`docker compose up`). Putting the scanner online needs three free accounts that are not created yet; the steps are in [docs/DEPLOY.md](docs/DEPLOY.md). See [PROGRESS.md](PROGRESS.md) for what was checked and how.
>
> **Live site:** https://thebhardwajrohit.github.io/LinkLens/ (homepage only, until a public scan server exists)

## What a scan does

1. Checks known blacklists first (Google Safe Browsing, the Phishing.Database lists, and more), for an answer in about two seconds.
2. Opens the link in a locked-down sandbox browser and follows every redirect.
3. Looks up who is behind it: domain age, registrar, server location, hosting network, certificate.
4. Fingerprints the page and compares it with about 55,000 known pages to find its scam family and sibling sites.
5. Places the site in a link graph (who links to it, whom it links to) and reads what the neighbours say about it.
6. Scores it with plain rules, plus a trained model as one more opinion (97.5% precision and 75.9% recall on 15,558 pages it had never seen). The model is never trusted alone: [docs/MODEL_REPORT.md](docs/MODEL_REPORT.md) explains why and shows the numbers.
7. Shows a verdict, the scam type, every reason in plain words, a network map, and a report you can save as a PDF.

Results are likely, not certain, and the report always says why.

## How it's put together

| Part | What it does | Runs on |
|---|---|---|
| `web/` | The website (Vite, React, TypeScript, Tailwind) | GitHub Pages |
| `api/` | Runs scans and serves results (Python, FastAPI) | Docker |
| `sandbox/` | The only part that visits target links (Playwright + Chromium) | Docker, isolated network |
| `jobs/` | Data jobs: dataset loading, feed ingestion, family grouping, model training ([jobs/README.md](jobs/README.md)) | GitHub Actions, or Docker |
| Database | Scans, fingerprints, families | Postgres (local in dev, Supabase later) |

Why each choice was made: [docs/TECH_DECISIONS.md](docs/TECH_DECISIONS.md).

## Run it locally

You need Docker Desktop.

```bash
cp .env.example .env    # then add any API keys you have (all optional)
docker compose up --build
```

- Website: http://localhost:3000
- API health check: http://localhost:8000/health
- API docs: http://localhost:8000/docs

### Working on one part without Docker

Website, with live reload on http://localhost:5173:

```bash
cd web
npm install
npm run dev
```

Website tests:

```bash
cd web
npm test
```

Sandbox tests (inside the sandbox image, with networking off):

```bash
docker build --target test -t linklens-sandbox-test ./sandbox
docker run --rm --network none linklens-sandbox-test
```

API tests:

```bash
cd api
python -m venv .venv
.venv/Scripts/activate      # on Linux or macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## Safety rules

LinkLens handles live scam links, so a few rules never bend:

- Only the sandbox visits target links. It has its own network, no secrets, and no access to the database.
- Every link and every redirect is checked, so nothing can trick us into reaching private or internal addresses.
- The sandbox never types, submits forms, runs downloads, or gets around CAPTCHAs.
- Captured pages are shown as screenshots only. Links from them are shown defanged (`hxxp://example[.]com`) and are not clickable.
- Tests never touch live scam links.

## Docs

- [CLAUDE.md](CLAUDE.md): short project summary and working rules
- [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md): the full original plan
- [docs/DATASETS.md](docs/DATASETS.md): research datasets we plan to use
- [docs/TECH_DECISIONS.md](docs/TECH_DECISIONS.md): every stack choice and why
- [docs/MODEL_REPORT.md](docs/MODEL_REPORT.md): how the scoring model was trained, how well it does, and where it is weak
- [docs/DEPLOY.md](docs/DEPLOY.md): putting LinkLens online for free, step by step
- [jobs/README.md](jobs/README.md): the data jobs (dataset loading, feed ingestion, family grouping, training, the real-site check)

## Credits

- This product includes GeoLite Data created by MaxMind, available from https://www.maxmind.com.
- Domain and IP registration data: RDAP servers listed by [IANA](https://data.iana.org/rdap/).
- Certificate history: [crt.sh](https://crt.sh/) and [Cert Spotter](https://sslmate.com/certspotter/).
- Blacklists: [Google Safe Browsing](https://developers.google.com/safe-browsing/v4/advisory) (advisory provided by Google), [Phishing.Database](https://github.com/Phishing-Database/Phishing.Database) (MIT license), [urlscan.io](https://urlscan.io/) search. VirusTotal and URLhaus switch on when you add a free key.
- Site popularity: the [Tranco list](https://tranco-list.eu/) (Le Pochat et al., NDSS 2019). The list ID used is shown on each report.
- Page library and model training data: [PhreshPhish](https://huggingface.co/datasets/phreshphish/phreshphish) (Dalton et al., 2025, CC BY 4.0). Only fingerprints and feature numbers are kept, never the pages.
- Link-graph method: SiNMULI (Gayen, Mondal, Jana, [arXiv:2608.19190](https://arxiv.org/abs/2608.19190)).
- Server map: [Leaflet](https://leafletjs.com/) with map data from [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors. Network map: [Cytoscape.js](https://js.cytoscape.org/).

To get server locations locally, put your free MaxMind account ID and license key in `.env`. The API downloads the GeoLite2 databases into a Docker volume and refreshes them weekly. Without a key, everything else still works.

## License

Code: [MIT](LICENSE). Datasets keep their own licenses (listed in [docs/DATASETS.md](docs/DATASETS.md)).

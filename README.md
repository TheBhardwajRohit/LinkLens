# LinkLens

**Paste a link. See who's really behind it.**

LinkLens checks a suspicious link safely and tells you:

- how dangerous it is (a score out of 100)
- what kind of scam it is (fake bank login, crypto scam, fake prize, and more)
- which scam family it belongs to, and which other sites are run by the same people
- where the server is, who hosts it, and who registered the domain
- why it was flagged, in plain words

You never open the page yourself. A locked-down sandbox browser visits it and takes a screenshot.

> **Status:** phase 4 of 10. Scans work on a local install: the sandbox opens the link, recon finds who's behind it, and LinkLens gives a verdict (Safe, Suspicious, or Likely dangerous), a score out of 100, the scam type, and every reason in plain words. Progress shows live, and every result gets a link to reopen it. See [PROGRESS.md](PROGRESS.md).
>
> **Live site:** https://thebhardwajrohit.github.io/LinkLens/ (homepage only; the scanner runs locally for now)

## How it's put together

| Part | What it does | Runs on |
|---|---|---|
| `web/` | The website (Vite, React, TypeScript, Tailwind) | GitHub Pages |
| `api/` | Runs scans and serves results (Python, FastAPI) | Docker |
| `sandbox/` | The only part that visits target links (Playwright, from phase 2) | Docker, isolated network |
| `jobs/` | Scheduled data collection and family grouping | GitHub Actions |
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

## Credits

- This product includes GeoLite Data created by MaxMind, available from https://www.maxmind.com.
- Domain and IP registration data: RDAP servers listed by [IANA](https://data.iana.org/rdap/).
- Certificate history: [crt.sh](https://crt.sh/) and [Cert Spotter](https://sslmate.com/certspotter/).
- Site popularity: the [Tranco list](https://tranco-list.eu/) (Le Pochat et al., NDSS 2019). The list ID used is shown on each report.
- Research datasets are credited here once they're loaded (phase 6).

To get server locations locally, put your free MaxMind account ID and license key in `.env`. The API downloads the GeoLite2 databases into a Docker volume and refreshes them weekly. Without a key, everything else still works.

## License

Code: [MIT](LICENSE). Datasets keep their own licenses (listed in [docs/DATASETS.md](docs/DATASETS.md)).

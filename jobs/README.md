# jobs

Data jobs: plain Python scripts that fill the page library. They reuse the API's own code
(`api/app`), so a dataset page or a feed page is read exactly like a scanned page.

| Job | Script | Runs | What it does |
|---|---|---|---|
| Dataset load | `seed_phreshphish.py` | By hand (workflow "Load dataset", or Docker) | Streams rows of the PhreshPhish research dataset, fingerprints each page, stores the fingerprints and writes the feature file the model is trained from. The HTML is thrown away. |
| Feed ingestion | `ingest.py` | Hourly on GitHub Actions (workflow "Feed ingestion") | Picks new links from free scam feeds, opens each in the sandbox, stores fingerprints and who is behind the page. |
| Family grouping | `cluster.py` (phase 7) | Nightly | Groups stored pages into scam families. |
| Model training | `train.py` (phase 9) | By hand | Trains and checks the scoring model. |

## Run one locally (Docker)

```bash
docker compose --profile jobs build jobs
docker compose run --rm jobs python -m jobs.seed_phreshphish --split train --limit 2000
```

The jobs container sees the local database, the Tranco list, and an `ml_data` volume for feature
files. Dataset pages are phishing HTML, so never run the dataset job directly on Windows: the
antivirus may quarantine files mid-download. Docker and GitHub Actions are fine.

## Feed ingestion has three steps

```
plan    reads the feeds, picks links not seen before        may read the database
visit   opens each link in the sandbox, fingerprints it     no secrets, no token permissions
store   looks up who is behind each page, saves the row     database and MaxMind key
```

The visit step is the only one that touches live scam pages, so it gets no secrets at all. Raw
HTML and full screenshots stay inside it. Only fingerprints, a few facts, and a small thumbnail
move on to the store step.

**Never run the visit step on a personal computer or a campus network** (safety rule 10). It is
made for GitHub Actions runners or a separate server.

## Turning the hourly schedule on

The schedule is skipped until two things exist in the GitHub repository settings
(Settings, Secrets and variables, Actions):

1. Secret `DATABASE_URL`: the Supabase connection string.
2. Variable `INGEST_ENABLED` set to `true`.

Optional: secrets `MAXMIND_ACCOUNT_ID` and `MAXMIND_LICENSE_KEY` (server locations), variable
`FEEDS` (comma-separated feed names; the default is `phishing_database`).

Without a database, a manual run with "dry run" ticked still tries the whole chain and prints
what it would have stored.

## Feeds

| Name | Source | On by default | Notes |
|---|---|---|---|
| `phishing_database` | [Phishing.Database](https://github.com/Phishing-Database/Phishing.Database) | Yes | MIT license. New links first, then a random handful from the active list. |
| `openphish` | OpenPhish community feed | No | Its terms allow personal research only and forbid passing the data on, so it stays off unless you add it to `FEEDS` for private use. |

Each run takes at most 40 links, one per site, so the volume stays modest.

## Tests

```bash
cd jobs
pip install -r ../api/requirements-dev.txt
pytest
```

The tests use made-up pages and fake sandbox results. They never open a real scam link.

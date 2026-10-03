# jobs

Data jobs: plain Python scripts that fill the page library. They reuse the API's own code
(`api/app`), so a dataset page or a feed page is read exactly like a scanned page.

| Job | Script | Runs | What it does |
|---|---|---|---|
| Dataset load | `seed_phreshphish.py` | By hand (workflow "Load dataset", or Docker) | Streams rows of the PhreshPhish research dataset, fingerprints each page, stores the fingerprints and writes the feature file the model is trained from. The HTML is thrown away. |
| Feed ingestion | `ingest.py` | Hourly on GitHub Actions (workflow "Feed ingestion") | Picks new links from free scam feeds, opens each in the sandbox, stores fingerprints and who is behind the page. |
| Family grouping | `cluster.py` | Nightly on GitHub Actions (workflow "Family grouping") | Links pages whose fingerprints agree and groups them into scam families, named after the brand they target. |
| Model training | `train.py` | By hand, in Docker | Trains the page-reading model from the feature files, checks it on the test split and on the saved real honest pages, and writes `api/app/ml/model.json` and `docs/MODEL_REPORT.md`. |
| Real-site check | `honest_check.py` | By hand, in Docker, with the local scan server running | Sends the well-known honest pages listed in `data/honest_sites.txt` to the scan server and saves the numbers the model reads, so training can report how the model rates pages from outside the dataset. |

## Run one locally (Docker)

```bash
docker compose --profile jobs build jobs
docker compose run --rm jobs python -m jobs.seed_phreshphish --split train --limit 2000
```

Group the families and train the model:

```bash
docker compose run --rm jobs python -m jobs.cluster
docker compose run --rm -v "$PWD/api/app/ml:/out/ml" -v "$PWD/docs:/out/docs" jobs \
  python -m jobs.train --out-model /out/ml/model.json --out-report /out/docs/MODEL_REPORT.md
```

## After changing the model's features

The feature files hold numbers worked out by `api/app/ml/features.py`. If that file changes, or a
rule that feeds it, load both splits again before training (about 30 minutes), or the model would
be trained on one set of numbers and used on another:

```bash
docker compose --profile jobs build jobs
docker compose run --rm jobs python -m jobs.seed_phreshphish --split train --limit 40000
docker compose run --rm jobs python -m jobs.seed_phreshphish --split test --limit 16000
```

The training job refuses feature files written by older code. A test in the API
(`test_the_shipped_model_fits_the_feature_list`) fails until the model is trained again.

## Checking the model on real honest pages

The dataset's honest pages are mostly large pages of popular sites, so its test split says
little about a small honest site. `honest_check.py` fills that gap with about a hundred real
pages. It never opens a site itself: it asks the scan server, whose sandbox does the visiting.

```bash
docker compose up -d
docker compose exec api python -m app.access create "honest check"    # prints a key once
docker compose run --rm -e LINKLENS_API_KEY=<the key> jobs python -m jobs.honest_check collect
docker compose run --rm jobs python -m jobs.honest_check report
```

The saved pages (no HTML, only the link and page facts) live in the `ml_data` volume, and the
next training run puts the result in `docs/MODEL_REPORT.md`. Revoke the key afterwards with
`python -m app.access revoke <id>`.

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

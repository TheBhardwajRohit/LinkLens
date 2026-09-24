# jobs

Scheduled jobs, run by GitHub Actions (workflows in `.github/workflows/`). Empty until phase 6.

Planned:

| Job | When | What |
|---|---|---|
| Feed ingestion | Every 30 to 60 min | Pull new URLs from free phishing feeds, drop ones already seen, visit new ones in the sandbox, store fingerprints and recon |
| Nightly clustering | Once a night | Group stored pages into scam families |
| Dataset seeding | Manual trigger | Stream research datasets, compute fingerprints, store them |

Each job is a plain Python script, so it can also run on any server if it ever has to move off Actions.

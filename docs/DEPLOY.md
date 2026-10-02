# Putting LinkLens online

Everything here is free for a student, and nothing here has been done yet. Each part needs an
account that only Rohit can create. The parts are independent: do one, stop, and the project
still works.

| Part | What it gives you | Account needed | Cost |
|---|---|---|---|
| 1. Shared database | The page library and saved scans live online; the hourly feed job can run | Supabase (free plan) | Free: 500 MB database |
| 2. Hourly data jobs | New scam pages are added every hour, families regrouped every night | None beyond part 1 | Free: public repo minutes |
| 3. Scan server | The live site can scan links for anyone | Azure for Students (no card) | Free grant, see below |
| 4. Point the site at it | The GitHub Pages site stops saying "scanner offline" | None | Free |

**Honest note:** parts 1, 2, and 4 use things already tested in this repo (the jobs ran on GitHub
Actions in a dry run). The Azure commands in part 3 follow Microsoft's documentation as read on
3 October 2026, but have not been run on a real subscription. Expect to adjust a detail or two.

## 1. Shared database (Supabase)

1. Create a free project at https://supabase.com. Pick a region close to India (Mumbai or Singapore).
2. In the project, open **Connect** and copy the **Session pooler** connection string. It looks
   like `postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`.
   Use the session pooler, not the direct connection: GitHub's runners only speak IPv4, and the
   direct connection is IPv6 unless you pay for an add-on.
3. In the GitHub repo: **Settings, Secrets and variables, Actions, New repository secret**.
   Name `DATABASE_URL`, value: that connection string.

The tables are created by the first job that connects. Nothing else to set up.

Things to know about the free plan: 500 MB of database, and a project is paused after a week
with no activity. The hourly job counts as activity.

## 2. Hourly data jobs

1. Load the starting data once: **Actions, Load dataset, Run workflow**. Start with `train` and
   20,000 rows (about 25 minutes). You can run it again with `skip` set to continue.
2. Group the families once: **Actions, Family grouping, Run workflow**.
3. Switch the schedules on: **Settings, Secrets and variables, Actions, Variables, New repository
   variable**. Name `INGEST_ENABLED`, value `true`.

From then on, feed ingestion runs every hour at minute 17 and family grouping every night.
Optional secrets: `MAXMIND_ACCOUNT_ID` and `MAXMIND_LICENSE_KEY` (server locations for feed pages).

To pause everything, delete the `INGEST_ENABLED` variable.

Watch the database size on Supabase's dashboard. A stored page is about 1 kB, and a thumbnail a
few kB (thumbnails from feeds are dropped after 30 days). 100,000 pages take roughly 150 MB.

## 3. Scan server (Azure Container Apps)

Why this host: it runs containers as they are, scales to zero when nobody is scanning (so it
costs nothing while idle), and the free grant is per month, every month:
180,000 vCPU-seconds, 360,000 GiB-seconds, and 2 million requests. A scan keeps the sandbox
(2 vCPU, 4 GB) busy for about 30 seconds, so the grant covers roughly 2,000 to 3,000 scans a month.
The Azure for Students offer adds USD 100 of credit and needs no credit card.

### 3a. Publish the two containers

**Actions, Publish images, Run workflow.** This builds the API and the sandbox and pushes them
to the GitHub Container Registry as `ghcr.io/thebhardwajrohit/linklens-api` and
`ghcr.io/thebhardwajrohit/linklens-sandbox`. Then make both packages public (on your GitHub
profile: **Packages**, open each one, **Package settings, Change visibility**), so Azure can
pull them without a password.

### 3b. Create the apps

Install the Azure CLI, then:

```bash
az login
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights

az group create --name linklens --location centralindia
az containerapp env create --name linklens-env --resource-group linklens --location centralindia
```

The sandbox first. It gets no secrets and is reachable only from inside the environment:

```bash
az containerapp create --name linklens-sandbox --resource-group linklens \
  --environment linklens-env \
  --image ghcr.io/thebhardwajrohit/linklens-sandbox:latest \
  --target-port 8100 --ingress internal \
  --cpu 2.0 --memory 4.0Gi --min-replicas 0 --max-replicas 1
```

Then the API. Replace the values in angle brackets. Secrets are stored by Azure, not in the image:

```bash
az containerapp create --name linklens-api --resource-group linklens \
  --environment linklens-env \
  --image ghcr.io/thebhardwajrohit/linklens-api:latest \
  --target-port 8000 --ingress external \
  --cpu 0.5 --memory 1.0Gi --min-replicas 0 --max-replicas 1 \
  --secrets database-url="<Supabase session pooler string>" \
            safe-browsing="<Google Safe Browsing key>" \
            maxmind-key="<MaxMind license key>" \
  --env-vars DATABASE_URL=secretref:database-url \
             GOOGLE_SAFE_BROWSING_API_KEY=secretref:safe-browsing \
             MAXMIND_ACCOUNT_ID=<MaxMind account id> \
             MAXMIND_LICENSE_KEY=secretref:maxmind-key \
             SANDBOX_URL=http://linklens-sandbox \
             CORS_ORIGINS=https://thebhardwajrohit.github.io \
             TRUST_FORWARDED_FOR=true \
             SCAN_RATE_LIMIT_PER_HOUR=10
```

The last command prints the API's public address (something like
`https://linklens-api.<random>.centralindia.azurecontainerapps.io`). Open `<address>/health` to check it.

Why each setting:

- `--ingress internal` on the sandbox: only the API can call it. It still reaches the internet to
  visit links, and its own guard still blocks every private address.
- `--min-replicas 0`: nothing runs, and nothing is billed, while nobody scans. The first scan after
  a quiet spell waits about 20 to 40 seconds for the containers to start.
- `--max-replicas 1`: scans in progress are tracked in the API's memory, so there must be one copy.
- `TRUST_FORWARDED_FOR=true`: Azure sits in front of the API, so the caller's real address comes
  from the header Azure adds. Never set this when the API is reachable directly.
- `SCAN_RATE_LIMIT_PER_HOUR=10`: keeps a public scanner inside the free grant.

Things that reset when the API scales to zero: scans in progress, the hourly limits, and the
in-memory caches. Saved scans, the page library, and blacklist answers stay in the database. The
MaxMind files and the phishing lists are downloaded again on the next start.

### 3c. Keys for scripts (optional)

To let a script scan more than the public limit, make it an API key. Run this once on your PC
with `DATABASE_URL` set to the Supabase string:

```bash
cd api
python -m app.access create "my script" --per-hour 200
```

The key is printed once. The script sends it in an `X-API-Key` header. `python -m app.access list`
shows the keys (never the key text), and `python -m app.access revoke <id>` switches one off.
To close the scanner to everyone without a key, set `REQUIRE_API_KEY=true` on the API (the
website then can't scan either).

## 4. Point the website at the scan server

**Settings, Secrets and variables, Actions, Variables, New repository variable.**
Name `VITE_API_URL`, value: the API's public address from step 3b (no slash at the end).
Then run **Actions, Deploy site, Run workflow**. The site's security policy is rebuilt to allow
that one address, and the scan box goes live.

To take the scanner offline again, delete the variable and redeploy the site.

## If something costs money

Nothing here should. If Azure ever shows a charge, run `az group delete --name linklens` and
everything in part 3 is gone. Supabase's free plan cannot be charged without adding a card.

## Running the scan server on your own PC instead

`docker compose up --build` still works exactly as before, and needs none of the above. To let
the live site use a scanner on your PC you would need a tunnel, which exposes your PC to the
internet. That is not recommended.

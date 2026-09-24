# Datasets for the head start

Checked on 2026-09-24 from each dataset's own page. Re-check the license before loading anything.

The goal: fill the database with known scam pages on day one, so Family Finder has something to match against while the cron jobs slowly collect fresh data.

## Load these (in this order)

| # | Dataset | What's inside | Size | Dates | License | Access |
|---|---|---|---|---|---|---|
| 1 | [Tranco list](https://tranco-list.eu/) | Top 1 million domains, ranked | Small zip | Updated daily | Mixed sources; one is CC BY-NC 4.0, so non-commercial use only (fine for us) | Direct download |
| 2 | [PhreshPhish](https://huggingface.co/datasets/phreshphish/phreshphish) | 666,315 rows: about 298k phishing, 368k benign. URL, HTML, label, **target brand**, date, language | 36.6 GB | Up to Dec 2025 (v1.0.1 added about 200k samples from Mar to Dec 2025) | CC BY 4.0 | Hugging Face, no sign-up gate, can be streamed |
| 3 | [Phishpedia](https://github.com/lindsey98/Phishpedia) | 30,000 phishing sites: URL, HTML, **screenshot**, target brand | Not stated | Older (2021 paper) | Repo is CC0-1.0; confirm the data files carry the same | Google Drive link in the repo |
| 4 | [Zenodo 21379702](https://zenodo.org/records/21379702) (Yadav et al.) | 60,000 URLs (31,641 phishing, 28,359 legit), 18 URL features, 21,311 **screenshots** | 1.8 GB | Published July 2026 | CC BY 4.0 | Direct download |
| 5 | [Ariyadasa et al.](https://data.mendeley.com/datasets/n96ncsr5g4/1) | 80,000 pages (30k phishing, 50k legit): URL + HTML | Not stated | Sep to Oct 2021 | CC BY 4.0 | Direct download |
| 6 | [Zenodo 8041387](https://zenodo.org/records/8041387) (Putra) | 10,395 sites (5,151 phishing, 5,244 legit), 86 brands: screenshot, HTML, CSS, text, WHOIS, IP, SSL | 38.5 GB (22 zip files) | 2023 | CC BY 4.0 | Direct download |

### Why each one

- **Tranco:** our list of "known good" domains, and the brand list for lookalike-name checks (`paypa1.com` vs `paypal.com`). Needed early, from phase 3 or 4.
- **PhreshPhish:** the best head start. It's the biggest, the newest (data through 2025), and every row has the target brand, so families get names like "fake SBI login" for free. HTML only, no screenshots, so it feeds the HTML fingerprints (TLSH, DOM shape, text similarity) and the content rules.
- **Phishpedia and Zenodo 21379702:** these add the screenshots, which power the visual match (pHash, a perceptual hash where similar-looking images get similar hashes).
- **Ariyadasa:** this is the SiNMULI paper's own seed data. The links inside its HTML build the graph for phase 8.
- **Zenodo 8041387:** a small set of complete records (page plus WHOIS, IP, SSL). Useful for testing recon-based signals. It's large for its size, so we load it later if needed.

## Optional (skipped for now)

| Dataset | Why skipped |
|---|---|
| [PhiShark2026](https://arxiv.org/html/2608.23199) | The freshest and richest one (33,387 phishing scans from Apr to Aug 2026, with HTML, screenshot, favicon, redirects, TLS, DNS, WHOIS, GeoIP, ASN). But access needs an approval request ([phishark2026dataset.com](https://phishark2026dataset.com)). Worth applying if you're ever willing to wait. |
| [Phish360](https://web.cs.hacettepe.edu.tr/~selman/phish360-dataset/) | 10,748 samples (2020 to 2023) with URL, HTML, screenshot. Needs a Google Form request, and the page states no license. |
| [PILWD-134K](https://www.sciencedirect.com/science/article/pii/S0957417422012301) | 134,000 samples (2019 to 2020) with URL, HTML, screenshots, and an offline site copy. License not confirmed yet. |

## How we load them (phase 6)

- **Only fingerprints get stored.** A job downloads or streams each dataset, computes fingerprints and features, and saves those plus the URL, brand, date, and a small thumbnail. The raw files are thrown away and never go into git or Supabase.
- **Not directly on Windows.** Windows Defender may quarantine phishing HTML files mid-download. Process inside a Linux Docker container or a GitHub Actions runner.
- **Stream big datasets.** PhreshPhish can be read row by row from Hugging Face, so no 36 GB download is needed.
- **Filter to fit the free database (500 MB).** Load phishing rows first, newest first, and skip near-duplicates (same TLSH). Rough guess: 0.5 to 1 KB per stored page, so about 300k pages fit in 150 to 300 MB. We'll measure the real size in phase 6.
- **Credit the authors.** CC BY 4.0 requires attribution, so the README and the site's About page will list every dataset we use.

## Honest note

Old scam pages teach the system what families look like, but most live campaigns will use newer kits. PhreshPhish (2025) is the closest to current. The cron feeds close the gap over time.

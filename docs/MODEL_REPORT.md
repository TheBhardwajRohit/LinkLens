# Model report

Written by `jobs/train.py` on 2026-10-03. Results are measured on pages the model never saw.

## In short

- The model reads only the link and the page (the 78 numbers in `api/app/ml/features.py`).
- At its default cut-off (50%), it catches 75.9% of the scam pages in the test set,
  and 97.5% of the pages it flags really are scams. It wrongly flags 1.6% of honest pages.
- It is not trusted on its own. In a scan it can lift a page out of Safe only when the plain rules
  found warning signs too. Scored that way, rules and model together mark 41.2% of the test
  set's scam pages Suspicious or worse, and 1.0% of its honest pages.
- On 126 real honest pages from outside the dataset, the model alone rates 13 as likely scams (60% or more). In a scan, 1 of them ends up above Safe.
- These are results on a research dataset. Real links are harder, so the report page still says "likely".

Words used here: *precision* is the share of flagged pages that really are scams. *Recall* is the
share of all scams that were caught. *False alarms* is the share of honest pages wrongly flagged.

## Data

PhreshPhish v1.0.1 (CC BY 4.0), streamed and reduced to feature numbers by `jobs/seed_phreshphish.py`.

| Part | Pages | Scam | Honest | Dates |
|---|---|---|---|---|
| Training | 33,593 | 16,228 | 17,365 | 2024-07-02 to 2025-07-29 |
| Held back (to decide when to stop) | 5,929 | 1,579 | 4,350 | 2025-07-29 to 2025-09-08 |
| Test (the dataset's own test split) | 15,558 | 7,043 | 8,515 | 2025-09-08 to 2025-12-16 |

## What the dataset gets wrong, and what was done about it

The honest pages in the dataset are not like the honest pages people paste into a link checker.
They are mostly large inner pages of popular sites, while the scam pages are mostly small pages at
a bare site address:

| In the training data | Honest pages | Scam pages |
|---|---|---|
| The link is a bare site address (nothing after the site name) | 7.0% | 46.6% |
| The link has a query string (a part after "?") | 0.0% (1 of 21,715) | 7.4% |
| The page has under 100 tags | 6.2% | 40.4% |
| The site is on a free hosting service (github.io, weebly.com and the like) | 0.3% (65 of 21,715) | 30.6% |

A model trained on this as it is learns shortcuts that hold in the dataset but not on the web:
a query string, a bare address, a small page, or free hosting each means scam. Earlier versions
of this model did. The first called every one of 63 real honest pages a likely scam as soon as a
newsletter tag ("?utm_source=...") was added to its link. A later one, which still knew whether a
site was on free hosting, rated 8 of 17 real honest pages on github.io and similar services as
likely scams. Three things were done:

1. **The model never sees the query string**, nor the length of the whole link (which gives the
   query string away), nor whether the site is on a free hosting service. The dataset has next
   to no honest examples of either, so no weighting could fix them. The rules still use both,
   in the open.
2. **Honest pages count for more where they are rare.** Pages are grouped by size and by whether
   the link is a bare address. In a group where scam pages outnumber honest ones, each honest page
   is weighted up (at most 20 times) until both sides weigh the same. Being small, or being a bare
   address, then says nothing on its own. The groups are listed below.
3. **The model cannot raise a verdict alone.** See "Rules alone, and rules plus the model".

| Page size (tags) | Link | Honest pages | Scam pages | Each honest page counts as |
|---|---|---|---|---|
| under 40 | inner page | 217 | 1,152 | 5.31 |
| under 40 | bare address | 18 | 2,150 | 20 |
| 40 to 99 | inner page | 782 | 2,092 | 2.68 |
| 40 to 99 | bare address | 71 | 1,293 | 18.21 |
| 100 to 299 | inner page | 1,611 | 2,991 | 1.86 |
| 100 to 299 | bare address | 180 | 1,483 | 8.24 |
| 300 to 999 | inner page | 5,236 | 1,928 | 1 |
| 300 to 999 | bare address | 525 | 2,358 | 4.49 |
| 1,000 or more | inner page | 8,275 | 337 | 1 |
| 1,000 or more | bare address | 450 | 444 | 1 |

What the weights change, with everything else kept the same:

| | Without the weights | With the weights |
|---|---|---|
| Scam pages caught (50% cut-off) | 84.6% | 75.9% |
| Honest pages wrongly flagged | 3.3% | 1.6% |
| Honest pages under 100 tags wrongly flagged (517 in the test set) | 22.2% | 8.1% |
| Real honest pages rated 60% or more likely scam (of 126, see below) | 28 | 13 |

## Model

Gradient-boosted decision trees (LightGBM), 200 trees of up to 31 leaves, learning
rate 0.06. Training stopped when 30 more trees no longer helped on the held-back
pages. The model ships as plain JSON and is run by about 40 lines of Python, checked against LightGBM.

## Results on the test set

- ROC AUC: 0.9743 (1.0 is perfect ranking, 0.5 is guessing)
- PR AUC: 0.9721

At different cut-offs of the model's probability:

| | Precision | Recall | F1 | False alarms | Scams caught | Honest pages flagged | Scams missed |
|---|---|---|---|---|---|---|---|
| Flag when at least 95% | 99.7% | 35.9% | 52.8% | 0.1% | 2,528 | 7 | 4,515 |
| Flag when at least 80% | 99.3% | 57.1% | 72.5% | 0.3% | 4,020 | 28 | 3,023 |
| Flag when at least 60% | 98.3% | 69.6% | 81.5% | 1.0% | 4,905 | 84 | 2,138 |
| Flag when at least 50% | 97.5% | 75.9% | 85.4% | 1.6% | 5,347 | 137 | 1,696 |
| Flag when at least 40% | 96.7% | 79.7% | 87.4% | 2.2% | 5,610 | 189 | 1,433 |

When the model says 5% or less, 4.2% of those pages are scams anyway.
When it says 15% or less, 8.5% are.

The same test pages by size, at the 50% cut-off:

| Page size (tags) | Honest pages | Wrongly flagged | Scam pages | Caught |
|---|---|---|---|---|
| under 40 | 138 | 24 (17.4%) | 1,174 | 1,021 (87.0%) |
| 40 to 99 | 379 | 18 (4.7%) | 1,378 | 1,172 (85.1%) |
| 100 to 299 | 849 | 38 (4.5%) | 2,379 | 1,809 (76.0%) |
| 300 to 999 | 2,927 | 30 (1.0%) | 1,634 | 1,060 (64.9%) |
| 1,000 or more | 4,222 | 27 (0.6%) | 478 | 285 (59.6%) |

Small honest pages are still flagged far more often than large ones, and the test set holds few
of them, so those percentages are rough.

10,990 of the test pages (6,294 scam, 4,696 honest) are on sites that have no page at all in the
training data. On those alone, at the 50% cut-off, the model catches 77.6% of the scam pages and
wrongly flags 2.4% of the honest ones.

## Rules alone, and rules plus the model

The rule score here uses the link and page only (a dataset has no domain age, certificate,
blacklists, or scam family), so live scans have more to go on than this table shows.

How the model's opinion is added (`model_say` in `api/app/analysis/score.py`, the function a scan uses):

- 95% or more adds 50 points, 80% adds 40, 60% adds 25, 40% adds 10. 15% or less takes 10 off, 5% or less takes 20 off.
- When the rules alone scored under 8 (not counting the points for free hosting, which honest and
  scam sites share), the model may add at most 20, and never enough to leave
  Safe (0 to 30).
- On a free hosting service the model never adds more than 20, backed or not. The training data
  has 65 honest pages hosted that way, so there the model cannot tell honest from scam.
- On a brand's real site, or one of the 10,000 most visited sites, the model never adds points.
  336 of the test set's 7,043 scam pages sit on such sites.

| | Precision | Recall | F1 | False alarms | Scams caught | Honest pages flagged | Scams missed |
|---|---|---|---|---|---|---|---|
| Rules alone: Suspicious or worse (31+) | 75.6% | 6.1% | 11.4% | 1.6% | 433 | 140 | 6,610 |
| Rules + model: Suspicious or worse (31+) | 97.2% | 41.2% | 57.9% | 1.0% | 2,902 | 84 | 4,141 |
| Rules alone: Likely dangerous (70+) | 91.4% | 0.5% | 0.9% | 0.0% | 32 | 3 | 7,011 |
| Rules + model: Likely dangerous (70+) | 99.5% | 5.7% | 10.8% | 0.0% | 402 | 2 | 6,641 |

If the model always counted in full (no limits but the last one), the second row would catch 63.1% of the scam pages
and flag 1.1% of the honest ones. The difference is the price of not letting the model
raise a verdict alone. It looks large here because most scam pages in a dataset show no other
warning sign: there is no domain age, certificate, blacklist, or family to look at. A live scan
has those.

## Real honest pages from outside the dataset

126 well-known honest pages (small personal sites, software project pages, login pages, pages on
free hosting, Indian government services; the list is `jobs/data/honest_sites.txt`) were scanned through the
local scan server, last on 2026-10-03. The numbers the model reads were saved by
`jobs/honest_check.py`, so this part is worked out again every time the model is trained.

| | Pages |
|---|---|
| Honest pages checked | 126 |
| Rated 40% or more likely to be a scam page | 21 |
| Rated 60% or more | 13 |
| Rated 80% or more | 8 |
| Rated 95% or more | 0 |
| Above Safe in a scan (rules, model, and the limit together) | 1 |
| Above Safe if the model always counted in full | 5 |

3 of the 13 pages rated 60% or more have under 40 tags (7 pages that small were
checked). Very small honest pages are the model's weak spot, and the reason it cannot raise a
verdict alone.

Still above Safe: `learngitbranching.js.org` (score 38).

This is a sanity check, not a clean test. The list is short and hand-picked, and it was looked at
while the fixes above were chosen.

## What the model leans on most

| Signal | Share of the model's total gain |
|---|---|
| the number of other sites it links to (`out_domains`) | 16.9% |
| the number of links on the page (`links`) | 8.6% |
| the layers of subdomains (`subdomain_depth`) | 7.3% |
| the length of the site name (`host_length`) | 5.5% |
| how deep the link's path goes (`path_depth`) | 5.4% |
| the length of the link's path (`path_length`) | 4.2% |
| the number of scripts (`scripts`) | 4.1% |
| a domain ending scammers use often (`abused_tld`) | 4.0% |
| the share of links to other sites (`external_link_share`) | 3.9% |
| the size of the page (`tags_log`) | 3.6% |
| how random the name looks (`entropy`) | 3.3% |
| the brand names on the page (`brands_mentioned`) | 3.2% |
| the share of links that go nowhere (`empty_link_share`) | 3.1% |
| whether the link uses HTTPS (`https`) | 2.9% |
| the scripts loaded from other sites (`external_scripts`) | 2.2% |

## Honest limits

- The weights reduce what the model learns from page size, but they cannot add what is missing:
  the training data holds only 235 honest pages under 40 tags.
- The limit on the model costs recall. A scam page that shows no other warning sign is not
  flagged by the model alone.
- Scam kits are copied many times. Copies of one kit can sit in both the training and the test
  set, which makes the test easier than brand-new kits would be.
- The model sees the page as the sandbox captured it. Pages that show different content to
  scanners are judged on what was shown. On a bot-check screen the model says nothing.
- It does not use who registered the domain, the server, blacklists, or scam families. Those are
  added by the rules, which is why the final score combines both.
- Popularity, the query string, and free hosting are left out of the model on purpose (see
  `api/app/ml/features.py`).

# Sleeper Fantasy Bridge

A read-only daily scouting report for **The 40 year dash** and **ItsFuckinBmore**.

## What works

- Fetches your exact roster by stable user ID, including bench and reserve players.
- Reads completed waiver/free-agent transactions across season weeks and lists drops that remain unrostered.
- Filters the top 100 global trending adds against every league roster, reserve, and taxi list.
- Prioritizes watchlist players who match empty or unavailable starting slots, then sorts by global add count.
- Generates a Markdown report with player names, injury metadata, scoring context, and the full roster.
- Runs tests and generates a report when application code is pushed to main.
- Schedules a daily report for **6:00 AM America/New_York**, including daylight saving time.
- Supports optional SMTP email delivery; email is disabled until configured.

## Read your report on GitHub

1. Open **Actions** in this repository.
2. Select **Daily Sleeper report**.
3. Open the latest successful run. The report appears in its summary.
4. The report is also available as a downloadable artifact, retained for 30 days.

For an immediate report, select **Run workflow** on the workflow page and run it on `main`.

GitHub scheduled jobs can be delayed and are not a guarantee of exact 6:00 AM delivery. Public repositories may have scheduled workflows disabled after 60 days without repository activity. Check the Actions page if reports stop.

## League configuration

| Setting | Default |
|---|---|
| League | The 40 year dash |
| League ID | `1388592505368363009` |
| Sleeper username | `ItsFuckinBmore` |
| Stable user ID | `326127889974034432` |
| Verified roster at setup | 7; resolved dynamically on each run |
| Scoring at setup | Half-PPR; live settings shown in reports |
| Report timezone | America/New_York |

Optional repository **Actions variables** `SLEEPER_LEAGUE_ID` and `SLEEPER_USER_ID` override these defaults. Update the league ID after annual renewal. The program rejects a league from a different NFL season and fails if it cannot identify exactly one matching roster.

## Run locally

Install Python 3.11 or newer. On Linux, the application uses only the Python standard library. On Windows, install timezone data first:

```sh
python -m pip install tzdata
```

From the repository directory:

```sh
python -m unittest -v
python bridge.py --preview
python bridge.py
```

The preview writes `reports/latest.md` without advancing the report checkpoint. A normal run writes the report and updates `data/state.json`. Both modes may refresh the player metadata cache. Local configuration uses environment variables; `.env` files are not loaded automatically.

## Enable email delivery (optional)

Use an SMTP provider that supports STARTTLS on port 587. Add these repository **Actions secrets** under **Settings → Secrets and variables → Actions**:

- `SMTP_HOST`
- `SMTP_USERNAME`
- `SMTP_PASSWORD` (use the provider's app password where required)
- `EMAIL_FROM`
- `EMAIL_TO`

Then add the Actions **variable** `ENABLE_EMAIL` with value `true`. This enables email for scheduled and manually requested runs. Code pushes generate reports without emailing them. Run the workflow manually to test delivery once you have configured your own destination.

Never put passwords in the README or source files. No email is sent by default. For local delivery, export the same secrets as environment variables and run `python notify.py` after generating a report. Local SMTP port can be overridden with `SMTP_PORT`.

## State and reliability

Sleeper reads retry temporary failures three times. A required API failure stops the report instead of presenting partial results as complete. GitHub marks failed workflow runs visibly; enable GitHub Actions failure notifications in your own account settings if desired.

The first run reports drops from the previous 24 hours. Later runs report drops since the last successful saved report checkpoint. All weeks from 0 through the current week (up to 18) are queried so week boundaries and missed days can be recovered. Trades and failed/pending transactions are excluded. Repeat transaction IDs are deduplicated within each report, and players reclaimed by another team are excluded.

GitHub Actions caches retain checkpoints, the email ledger, and player metadata between runs. **Caches can be evicted**: if state is lost, the next report falls back to 24 hours and may repeat previously reported activity. A durable database is a future improvement. Player metadata is refreshed at most once per 24 hours.

Email delivery is skipped if the ledger already records that league/report date/recipient. A crash after the SMTP server accepts a message but before the ledger is saved can still cause a duplicate; SMTP does not provide guaranteed exactly-once delivery. A failed email step prevents saving the new checkpoint so a retry can recover the report window.

## Recommendation limits

The watchlist is an explainable scouting heuristic, **not a projection-based add/drop engine**. League scoring is displayed but is not yet used to calculate projected fantasy points. No bye-week feed, current news feed, or projection source is configured. Injury metadata can be up to 24 hours old.

The report intentionally does not claim that a trending player is better than someone on your bench and does not recommend a specific drop without supporting evidence. Add a validated ranking/projection source before using this as an upgrade model.

Unrostered means absent from roster, reserve, and taxi holdings. It does not prove a player can be added immediately: check waiver locks, budgets, eligibility, and claim deadlines in Sleeper. This application never submits claims or changes rosters.

## Files

- `bridge.py`: Sleeper data collection, filtering, and report generation.
- `notify.py`: optional SMTP email delivery and duplicate suppression.
- `test_bridge.py`, `test_notify.py`, `test_integration.py`: offline tests with no notifications sent.
- `.github/workflows/daily-report.yml`: tests, report generation, daily schedule, artifacts, and optional email.

## Next improvements

- Add current projections and bye-week data for scoring-aware add/drop comparisons.
- Add durable storage for stronger recovery and delivery tracking.
- Add alternate notification channels if needed.

## Sources

- [Sleeper API documentation](https://docs.sleeper.com/)
- [GitHub scheduled workflow documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

Sleeper's documented API is read-only and does not require an API token.

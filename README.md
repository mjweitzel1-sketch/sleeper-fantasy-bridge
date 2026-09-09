# Sleeper Fantasy Bridge

A planned fantasy football assistant for monitoring **The 40 year dash**, identifying dropped players and trending available players, and producing recommendations tailored to my exact roster.

## Current Status

This repository currently contains only this README. Application code, installation steps, report generation, notifications, and scheduled workflows have not been implemented.

## League and Team

| Setting | Value |
|---|---|
| League name | The 40 year dash |
| League ID | `1388592505368363009` |
| Season | 2026 |
| Sleeper username | `ItsFuckinBmore` |
| Sleeper user ID | `326127889974034432` |
| Roster ID | `7` |
| League size | 10 teams |
| Scoring | Half-PPR |
| Starting lineup | QB, 2 RB, 2 WR, TE, 2 FLEX, DEF |
| Bench | 6 slots |
| Reserve | 1 slot |
| Desired report time | 6:00 AM America/New_York |
| Notification destination | To be selected |

League settings and roster ownership should be verified from Sleeper on each run. The league ID should be reviewed when the league renews for a new season.

## Planned Features

### Dropped Player Monitoring

- Retrieve completed league transactions.
- Identify dropped players and when they were dropped.
- Check whether each dropped player is still unrostered.
- Distinguish waiver candidates from players available for immediate pickup.
- Save transaction history to prevent duplicate reporting.
- Handle week changes and recover transactions missed between runs.

### Trending Available Players

- Retrieve Sleeper’s trending player adds.
- Exclude players already owned by any team in this league.
- Account for bench, reserve, and taxi holdings where applicable.
- Show trending activity alongside relevant player information.
- Treat popularity as a signal, not proof that a player improves my roster.

### Roster-Specific Recommendations

- Resolve my team using my stable Sleeper user ID.
- Read my current starters, bench, and reserve players.
- Apply the league’s actual scoring and lineup settings.
- Evaluate positional needs, injuries, bye weeks, and roster depth.
- Explain why each suggested pickup could help.
- Identify a corresponding drop candidate when a roster move requires one.
- Clearly state uncertainty and the sources used for rankings or projections.
- Recommend no move when no meaningful upgrade is supported.

### Daily Report and Notifications

Produce a report containing:

1. Report time and data freshness.
2. My roster summary and priority needs.
3. Newly dropped players who remain unrostered.
4. Trending players available in this league.
5. Ranked pickup recommendations with reasoning.
6. Suggested corresponding drops, where justified.
7. Any missing data or collection failures.

Target delivery is **6:00 AM America/New_York**, with daylight saving time handled automatically.

The notification destination must be configured before delivery is enabled. Scheduled GitHub Actions runs may be delayed, so exact delivery at 6:00 AM is not guaranteed.

## Data Sources

The initial integration will use the [Sleeper API](https://docs.sleeper.com/).

Relevant endpoints include:

- User: `/v1/user/{username_or_user_id}`
- League: `/v1/league/{league_id}`
- Rosters: `/v1/league/{league_id}/rosters`
- League users: `/v1/league/{league_id}/users`
- Transactions: `/v1/league/{league_id}/transactions/{week}`
- NFL state: `/v1/state/nfl`
- Player information: `/v1/players/nfl`
- Trending adds: `/v1/players/nfl/trending/add`

Sleeper’s documented API is read-only and does not require an API token. This project will recommend moves; it will not submit waiver claims or modify a roster.

Additional ranking, projection, injury, or bye-week sources may be needed for stronger recommendations. These sources have not yet been selected.

## Planned Configuration

The application should support the following configuration values. These are proposed settings, not currently implemented environment variables.

```dotenv
SLEEPER_LEAGUE_ID=1388592505368363009
SLEEPER_USERNAME=ItsFuckinBmore
SLEEPER_USER_ID=326127889974034432
REPORT_TIMEZONE=America/New_York
REPORT_TIME=06:00
```

Notification credentials must be stored in environment secrets or GitHub Actions secrets, never committed to this repository.

## Implementation Checklist

- [ ] Create the application and dependency configuration.
- [ ] Connect to Sleeper and validate league and roster ownership.
- [ ] Retrieve and cache player information.
- [ ] Collect completed transactions and identify drops.
- [ ] Persist processing history between runs.
- [ ] Filter trending players against all league rosters.
- [ ] Implement and document roster-specific ranking logic.
- [ ] Generate a readable daily report.
- [ ] Add a preview mode that does not send notifications.
- [ ] Configure a notification destination and delivery credentials.
- [ ] Add a timezone-aware daily workflow and manual run option.
- [ ] Prevent duplicate notifications on retries.
- [ ] Add failure handling and alerts.
- [ ] Test ownership filtering, duplicate transactions, week boundaries, and missing data.
- [ ] Document installation, configuration, and execution commands.

## Setup

Setup instructions will be added when the application exists. Editing this README does not activate monitoring or schedule notifications.

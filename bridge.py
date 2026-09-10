"""Read-only Sleeper daily scouting report. Python 3.11+, standard library only."""
import argparse
import json
import os
from pathlib import Path
import time
from collections import Counter
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo

API = 'https://api.sleeper.app/v1'
FLEX = {'FLEX': {'RB', 'WR', 'TE'}, 'SUPER_FLEX': {'QB', 'RB', 'WR', 'TE'},
        'REC_FLEX': {'WR', 'TE'}, 'WRRB_FLEX': {'WR', 'RB'}}


def get(path):
    for attempt in range(3):
        try:
            with urlopen(Request(API + path, headers={'User-Agent': 'SleeperFantasyBridge/1.0'}), timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                raise
            if attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def holdings(roster):
    return {str(pid) for key in ('players', 'reserve', 'taxi') for pid in roster.get(key) or [] if str(pid) != '0'}


def find_roster(rosters, user_id):
    matches = [r for r in rosters if r.get('owner_id') == user_id or user_id in (r.get('co_owners') or [])]
    if len(matches) != 1:
        raise ValueError('Expected exactly one roster for the configured user; check league and user IDs.')
    return matches[0]


def drops_since(transactions, since_ms, owned):
    result = {}
    for tx in transactions:
        if tx.get('status') != 'complete' or tx.get('type') not in ('waiver', 'free_agent'):
            continue
        stamp = tx.get('status_updated') or tx.get('created') or 0
        if stamp < since_ms:
            continue
        for pid, roster_id in (tx.get('drops') or {}).items():
            if pid not in owned:
                result[(str(tx['transaction_id']), pid)] = {'player_id': pid, 'roster_id': roster_id, 'time': stamp}
    return sorted(result.values(), key=lambda row: row['time'], reverse=True)


def clean(value):
    return str(value).replace('\n', ' ').replace('\r', ' ').replace('|', '/').replace('<', '&lt;').replace('>', '&gt;')


def label(pid, players):
    player = players.get(pid, {})
    return clean(player.get('full_name') or ' '.join(filter(None, [player.get('first_name'), player.get('last_name')])) or pid)


def position(pid, players):
    return players.get(pid, {}).get('position', '?')


def scouting(trending, owned, roster, players, slots):
    """Rank by concrete starting-slot gaps, then global add count, not projected value."""
    gaps = set()
    starters = roster.get('starters') or []
    for i, slot in enumerate(s for s in slots if s != 'BN'):
        pid = starters[i] if i < len(starters) else '0'
        injury = players.get(pid, {}).get('injury_status')
        if pid == '0' or injury in ('Out', 'IR', 'Doubtful', 'PUP', 'Sus'):
            gaps.update(FLEX.get(slot, {slot}))
    eligible = set().union(*(FLEX.get(s, {s}) for s in slots if s != 'BN'))
    counts = Counter(position(pid, players) for pid in holdings(roster))
    candidates = {}
    for row in trending:
        pid = str(row['player_id'])
        player = players.get(pid, {})
        pos = position(pid, players)
        if pid in owned or pos not in eligible or player.get('active') is False:
            continue
        candidates[pid] = {**row, 'player_id': pid, 'gap': pos in gaps,
                           'reason': ('Matches an empty or unavailable starting slot' if pos in gaps else 'Depth watch'),
                           'roster_count': counts[pos]}
    return sorted(candidates.values(), key=lambda r: (-int(r['gap']), -int(r.get('count', 0)), r['player_id']))


def render(league, roster, players, drops, candidates, now, since_ms, advanced=""):
    lines = [f"# {clean(league['name'])}: daily Sleeper report", '',
             f"Generated: {now.isoformat(timespec='seconds')}",
             f"Season: {league['season']} | Roster: {roster['roster_id']} | Reception points: {league.get('scoring_settings', {}).get('rec', 0)}", '',
             '## Your roster', '', '| Slot | Player | Position | Team | Injury status |', '|---|---|---|---|---|']
    starters = roster.get('starters') or []
    slots = [s for s in league['roster_positions'] if s != 'BN']
    entries = [(slots[i] if i < len(slots) else 'Starter', pid) for i, pid in enumerate(starters)]
    entries += [('Reserve' if pid in (roster.get('reserve') or []) else 'Taxi' if pid in (roster.get('taxi') or []) else 'Bench', pid)
                for pid in sorted(holdings(roster) - set(starters))]
    for slot, pid in entries:
        p = players.get(pid, {})
        lines.append(f"| {slot} | {'Empty' if pid == '0' else label(pid, players)} | {position(pid, players)} | {clean(p.get('team') or '-')} | {clean(p.get('injury_status') or 'None reported')} |")
    lines += ['', '## Dropped players still unrostered', '',
              f"Completed drops since {datetime.fromtimestamp(since_ms / 1000, now.tzinfo).isoformat(timespec='seconds')}. First run covers 24 hours; later runs cover time since the last saved report.", '']
    for row in drops:
        stamp = datetime.fromtimestamp(row['time'] / 1000, now.tzinfo).isoformat(timespec='minutes')
        lines.append(f"- **{label(row['player_id'], players)}** ({position(row['player_id'], players)}): dropped by roster {row['roster_id']} at {stamp}.")
    if not drops:
        lines.append('No completed drops in this window remain unrostered.')
    lines += ['', '## Roster-specific watchlist', '',
              'Priority is starting-slot need, then Sleeper global adds over 24 hours. These are scouting candidates, not projected upgrades.', '']
    for row in candidates[:15]:
        pid = row['player_id']
        p = players.get(pid, {})
        lines.append(f"- **{label(pid, players)}** ({position(pid, players)}, {clean(p.get('team') or 'no team')}): {row.get('count', 0)} adds. {row['reason']}; you roster {row['roster_count']} at this position. Injury: {clean(p.get('injury_status') or 'none reported')}.")
    if not candidates:
        lines.append('No eligible unrostered players found in the top 100 trending adds.')
    lines += ['', '## Limits and next action', '',
              '- Availability means absent from every roster, reserve, and taxi list. Check Sleeper for waiver locks and claim timing before acting.',
              '- No projections, bye-week feed, or verified news source is configured. No specific drop is recommended without evidence of an upgrade.',
              '- Player metadata is cached for up to 24 hours; roster, transaction, and trend data are fetched for this report.',
              '- Read-only: no claims or roster changes are submitted.', '', '[Source: Sleeper API](https://docs.sleeper.com/)', '']
    if advanced:
        lines = [line for line in lines if not line.startswith('- No projections,')]
    return '\n'.join(lines) + advanced


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', default='data/state.json')
    parser.add_argument('--output', default='reports/latest.md')
    parser.add_argument('--preview', action='store_true', help='Do not advance the saved report checkpoint')
    args = parser.parse_args()
    league_id = os.getenv('SLEEPER_LEAGUE_ID', '1388592505368363009')
    user_id = os.getenv('SLEEPER_USER_ID', '326127889974034432')
    now = datetime.now(ZoneInfo(os.getenv('REPORT_TIMEZONE', 'America/New_York')))
    state_path = Path(args.state)
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    identity = f'{league_id}:{user_id}'
    if state.get('identity') != identity:
        state = {}
    since_ms = state.get('last_report_ms', int(now.timestamp() * 1000) - 86400000)
    league = get(f'/league/{league_id}')
    if not league or league.get('sport') != 'nfl':
        raise ValueError('Configured NFL league was not found')
    nfl = get('/state/nfl')
    if str(league['season']) != str(nfl['season']):
        raise ValueError('League season differs from current NFL season; update SLEEPER_LEAGUE_ID after renewal')
    rosters = get(f'/league/{league_id}/rosters')
    roster = find_roster(rosters, user_id)
    owned = set().union(*(holdings(r) for r in rosters))
    cache = Path('data/players.json')
    if cache.exists() and time.time() - cache.stat().st_mtime < 86400:
        players = json.loads(cache.read_text(encoding='utf-8'))
    else:
        players = get('/players/nfl')
        write_json(cache, players)
    # Query all season weeks so multi-day outages and week boundaries do not lose drops.
    week = max(int(nfl.get('week') or 0), int(league.get('settings', {}).get('leg') or 0))
    transactions = []
    for leg in range(0, min(week, 18) + 1):
        transactions.extend(get(f'/league/{league_id}/transactions/{leg}'))
    trending = get('/players/nfl/trending/add?lookback_hours=24&limit=100')
    drops = drops_since(transactions, since_ms, owned)
    candidates = scouting(trending, owned, roster, players, league['roster_positions'])
    from recommendations import recommendation_section
    advanced = recommendation_section(league, roster, owned, players, nfl, now)
    report = render(league, roster, players, drops, candidates, now, since_ms, advanced)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding='utf-8')
    from report_formats import export_report
    export_report(output)
    if not args.preview:
        write_json(state_path, {'identity': identity, 'last_report_ms': int(now.timestamp() * 1000)})
    print(f'Report saved to {output}; {len(drops)} drops and {len(candidates)} watchlist candidates.')


if __name__ == '__main__':
    main()

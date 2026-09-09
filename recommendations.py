"""Free Sleeper projections plus nflverse schedule; conservative one-move comparisons."""
import csv
import io
import json
import math
import time
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError
from zoneinfo import ZoneInfo

PROJECTIONS = 'https://api.sleeper.com/projections/nfl'
SCHEDULE = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
POSITIONS = {'QB', 'RB', 'WR', 'TE'}
FLEX = {'FLEX': {'RB', 'WR', 'TE'}, 'SUPER_FLEX': POSITIONS,
        'REC_FLEX': {'WR', 'TE'}, 'WRRB_FLEX': {'WR', 'RB'}}
STATS = {'pass_yd', 'pass_td', 'pass_int', 'pass_2pt', 'rush_yd', 'rush_td', 'rush_2pt',
         'rec', 'rec_yd', 'rec_td', 'rec_2pt', 'fum', 'fum_lost', 'fum_rec_td'}
OTHER = {'sack', 'int', 'fum_rec', 'ff', 'safe', 'blk_kick', 'def_td', 'def_st_td',
         'def_st_ff', 'def_st_fum_rec', 'st_td', 'st_ff', 'st_fum_rec', 'xpm', 'xpmiss', 'fgmiss'}
ALIASES = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS'}


def team(value):
    return ALIASES.get(value, value)


def read_url(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'SleeperFantasyBridge/2.0'}), timeout=20) as response:
                return response.read().decode('utf-8-sig')
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def scored(rows, settings, season, week):
    if not isinstance(rows, list):
        raise ValueError('Projection response is not a player list')
    unknown = [k for k, v in settings.items() if v and k not in STATS | OTHER
               and not k.startswith(('pts_allow_', 'fgm_'))]
    if unknown:
        raise ValueError('Unsupported scoring rules: ' + ', '.join(sorted(unknown)))
    result = {}
    for row in rows:
        if str(row.get('season')) != str(season) or row.get('season_type', 'regular') != 'regular':
            continue
        if week is not None and str(row.get('week')) != str(week):
            continue
        stats = row.get('stats') or {}
        # ADP-only placeholder rows are not real projections.
        if not STATS.intersection(stats):
            continue
        values = {k: float(stats.get(k) or 0) for k in STATS}
        if not all(math.isfinite(v) for v in values.values()):
            continue
        result[str(row['player_id'])] = sum(values[k] * float(settings.get(k, 0)) for k in STATS)
    if not result:
        raise ValueError('No usable projections for the requested season/week')
    return result


def schedule(csv_text, season, week):
    games = [r for r in csv.DictReader(io.StringIO(csv_text)) if r['season'] == str(season) and r['game_type'] == 'REG']
    teams = {team(r[k]) for r in games for k in ('home_team', 'away_team')}
    if len(teams) != 32:
        raise ValueError('Season schedule is missing or incomplete')
    current = {}
    byes = {}
    for t in teams:
        played = {int(r['week']) for r in games if t in (team(r['home_team']), team(r['away_team']))}
        if len(played) != 17:
            raise ValueError('Season schedule is incomplete')
        byes[t] = sorted(set(range(1, 19)) - played)
    for r in games:
        if int(r['week']) == week:
            kick = datetime.fromisoformat(r['gameday'] + 'T' + r['gametime']).replace(tzinfo=ZoneInfo('America/New_York'))
            for side, other in [('home_team', 'away_team'), ('away_team', 'home_team')]:
                current[team(r[side])] = (kick, team(r[other]))
    if not current:
        raise ValueError('No games found for this week')
    return current, byes


def optimize(ids, players, scores, slots, locked=None):
    """Exact assignment by occupied-slot bitmask, with each player used once."""
    locked = locked or {}
    mask = sum(1 << i for i in locked)
    points = sum(scores.get(p, 0) for p in locked.values())
    dp = {mask: (points, dict(locked))}
    for pid in sorted(set(ids) - set(locked.values())):
        eligible = set(players[pid].get('fantasy_positions') or [players[pid].get('position')])
        for used, (total, lineup) in list(dp.items()):
            for i, slot in enumerate(slots):
                if used & (1 << i) or not eligible.intersection(FLEX.get(slot, {slot})):
                    continue
                new = used | (1 << i)
                value = total + scores[pid]
                if new not in dp or value > dp[new][0]:
                    dp[new] = (value, {**lineup, i: pid})
    # Empty slots score zero, but no player can occupy two FLEX slots.
    return max(dp.values(), key=lambda v: v[0])


def compare(roster, owned, players, weekly, season_points, slots, games, now):
    offensive_slots = [s for s in slots if s in POSITIONS or s in FLEX]
    if any(s not in POSITIONS | set(FLEX) | {'BN', 'DEF', 'K'} for s in slots):
        raise ValueError('Unsupported lineup position')
    if not offensive_slots:
        raise ValueError('No offensive lineup slots')
    reserve = set(roster.get('reserve') or []) | set(roster.get('taxi') or [])
    active = set(roster.get('players') or []) - reserve
    starters = set(roster.get('starters') or []) - {'0'}
    unavailable = {p for p, info in players.items() if info.get('injury_status') in ('Out', 'IR', 'PUP', 'Sus', 'Doubtful')}
    usable = {p for p in active if players.get(p, {}).get('position') in POSITIONS}
    scores = dict(weekly)
    for pid in usable:
        t = team(players[pid].get('team'))
        if pid in unavailable or (t and t not in games):
            scores[pid] = 0.0
        elif pid not in scores:
            raise ValueError('A roster player is missing a projection; withholding comparisons')
    locked = {}
    i = 0
    for index, slot in enumerate(s for s in slots if s != 'BN'):
        if slot not in POSITIONS and slot not in FLEX:
            continue
        starters_list = roster.get('starters') or []
        pid = starters_list[index] if index < len(starters_list) else '0'
        game = games.get(team(players.get(pid, {}).get('team')))
        if pid != '0' and game and game[0] <= now:
            if pid not in scores:
                raise ValueError('Locked starter projection unavailable')
            locked[i] = pid
        i += 1
    # Started bench players cannot enter a lineup for the current week.
    usable = {p for p in usable if p in locked.values() or not games.get(team(players[p].get('team'))) or games[team(players[p].get('team'))][0] > now}
    baseline, _ = optimize(usable, players, scores, offensive_slots, locked)
    protected = starters | reserve | unavailable
    protected.update(p.strip() for p in __import__('os').getenv('PROTECTED_PLAYER_IDS', '').split(',') if p.strip())
    bench = usable - protected
    capacity = len(slots)
    open_slot = len(active) < capacity
    results = []
    for add in sorted(set(weekly) - owned):
        info = players.get(add, {})
        if info.get('position') not in POSITIONS or info.get('active') is False or info.get('injury_status'):
            continue
        t = team(info.get('team'))
        if t not in games or games[t][0] <= now or add not in season_points:
            continue
        options = [None] if open_slot else sorted(bench)
        best = None
        for drop in options:
            if drop is not None:
                dropped = players[drop]
                # Same-position replacement preserves position depth; protect bye-week and unknown-value players.
                if dropped.get('position') != info.get('position') or dropped.get('injury_status'):
                    continue
                dt = team(dropped.get('team'))
                if dt not in games or games[dt][0] <= now or drop not in season_points:
                    continue
                if weekly[add] - scores[drop] < 3 or season_points[add] < season_points[drop] * 1.05:
                    continue
            changed = (usable - ({drop} if drop else set())) | {add}
            after, lineup = optimize(changed, players, scores, offensive_slots, locked)
            gain = after - baseline
            if gain >= 2 and add in lineup.values() and (best is None or gain > best['gain']):
                best = {'add': add, 'drop': drop, 'gain': gain, 'points': weekly[add],
                        'drop_points': scores.get(drop), 'opponent': games[t][1], 'baseline': baseline, 'after': after}
        if best:
            results.append(best)
    return sorted(results, key=lambda r: (-r['gain'], r['add']))[:5]


def recommendation_section(league, roster, owned, players, nfl, now):
    from bridge import label, clean
    lines = ['', '## Projection-based add/drop comparisons', '']
    try:
        week = int(nfl.get('display_week') or nfl.get('week') or 0)
        season = str(league['season'])
        if not 1 <= week <= 18 or nfl.get('season_type', 'regular') != 'regular':
            raise ValueError('Weekly recommendations are available during the regular season only')
        games, byes = schedule(read_url(SCHEDULE), season, week)
        if now < min(g[0] for g in games.values()) - timedelta(days=8) or now > max(g[0] for g in games.values()) + timedelta(hours=8):
            raise ValueError('NFL week and schedule are out of sync')
        query = '?season_type=regular&position[]=QB&position[]=RB&position[]=WR&position[]=TE'
        weekly = scored(json.loads(read_url(f'{PROJECTIONS}/{season}/{week}{query}')), league['scoring_settings'], season, week)
        annual = scored(json.loads(read_url(f'{PROJECTIONS}/{season}{query}')), league['scoring_settings'], season, None)
        moves = compare(roster, owned, players, weekly, annual, league['roster_positions'], games, now)
        lines += [f'Week {week}; projections and schedule fetched for this report at {now.isoformat(timespec="minutes")}.',
                  'Uses your league scoring and best legal offensive lineup, including both FLEX slots. D/ST and kickers are not compared.', '',
                  '**Alternatives, not a sequence of moves. Re-check waivers and news before acting.**', '']
        for move in moves:
            add, drop = move['add'], move['drop']
            action = f'Add **{label(add, players)}**'
            action += f'; consider dropping **{label(drop, players)}**' if drop else '; use your open roster slot'
            lines.append(f'- {action}: projects {move["points"]:.1f} points versus {clean(move["opponent"])}; best offensive lineup improves by **{move["gain"]:.1f} points**.')
            if drop:
                lines.append(f'  Drop candidate projects {move["drop_points"]:.1f}; incoming player also clears the season-projection guard. Bye weeks: incoming {byes.get(team(players[add].get("team")), [])}; outgoing {byes.get(team(players[drop].get("team")), [])}.')
        if not moves:
            lines.append('**Hold your roster:** no move clears the conservative thresholds with the available data. This is not a guarantee that no worthwhile move exists.')
        lines += ['', 'Guards: at least +2 best-lineup points, +3 individual weekly points for a swap, and incoming season projection at least 5% higher. Current starters, injured players, reserve/taxi players, bye-week drops, and already-started games are protected.',
                  'Season totals are a rough long-term guard, not rest-of-season rankings. Projections are estimates; provider update time is not guaranteed. No verified news feed or FAAB pricing is included.']
    except (ValueError, KeyError, TypeError, OverflowError, OSError) as exc:
        lines.append('**Comparisons unavailable:** ' + clean(str(exc))[:180] + '. The scouting report remains available; no projection-based move is advised.')
    lines += ['', '[Free projection endpoint](https://api.sleeper.com/projections/nfl) (undocumented by Sleeper; may change). [Schedule source: nflverse](https://github.com/nflverse/nfldata/blob/master/data/games.csv).', '']
    return '\n'.join(lines)

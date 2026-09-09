import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from recommendations import scored, optimize, compare, recommendation_section

class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 9, tzinfo=timezone.utc)
        self.players = {p: {'position': 'RB', 'team': 'BAL', 'full_name': p} for p in ('starter', 'bench', 'add')}
        self.roster = {'players': ['starter', 'bench'], 'starters': ['starter']}
        self.weekly = {'starter': 10, 'bench': 5, 'add': 16}
        self.annual = {'starter': 200, 'bench': 100, 'add': 150}
        self.games = {'BAL': (self.now + timedelta(days=1), 'PIT')}
    def moves(self, **kwargs):
        args = dict(roster=self.roster, owned={'starter', 'bench'}, players=self.players,
                    weekly=self.weekly, season_points=self.annual, slots=['RB', 'BN'], games=self.games, now=self.now)
        args.update(kwargs)
        return compare(**args)
    def test_half_ppr_and_custom_passing(self):
        row = {'player_id': 'a', 'season': '2026', 'week': 1, 'stats': {'rec': 4, 'rec_yd': 50, 'pass_td': 2, 'pass_int': 1}}
        self.assertEqual(scored([row], {'rec': .5, 'rec_yd': .1, 'pass_td': 4, 'pass_int': -1}, '2026', 1)['a'], 14)
        self.assertEqual(scored([row], {'pass_td': 6}, '2026', 1)['a'], 12)
    def test_wrong_week_and_adp_only_rejected(self):
        for row in [{'player_id': 'a', 'season': '2026', 'week': 2, 'stats': {'rec': 4}}, {'player_id': 'a', 'season': '2026', 'week': 1, 'stats': {'adp_dd_ppr': 999}}]:
            with self.assertRaises(ValueError): scored([row], {'rec': .5}, '2026', 1)
    def test_unsupported_scoring_rejected(self):
        with self.assertRaises(ValueError): scored([], {'bonus_rec_yd_100': 3}, '2026', 1)
    def test_flex_assignment_never_reuses_player(self):
        p = {'a': {'position':'RB'}, 'b': {'position':'WR'}, 'c': {'position':'TE'}}
        total, lineup = optimize(p, p, {'a':20,'b':15,'c':10}, ['RB','FLEX','FLEX'])
        self.assertEqual(total,45)
        self.assertEqual(len(set(lineup.values())),3)
    def test_real_lineup_improvement_with_named_bench_drop(self):
        move = self.moves()[0]
        self.assertEqual(move['drop'], 'bench')
        self.assertEqual(move['gain'], 6)
    def test_weekly_gain_alone_does_not_sacrifice_season_value(self):
        self.annual['bench'] = 200
        self.assertEqual(self.moves(), [])
    def test_injury_and_bye_and_missing_value_protect_drop(self):
        self.players['bench']['injury_status'] = 'Out'
        self.assertEqual(self.moves(), [])
        self.players['bench'].pop('injury_status')
        self.players['bench']['team'] = 'KC'
        self.assertEqual(self.moves(), [])
        self.players['bench']['team'] = 'BAL'
        self.annual.pop('bench')
        self.assertEqual(self.moves(), [])
    def test_missing_roster_projection_does_not_mean_zero(self):
        self.weekly.pop('bench')
        with self.assertRaises(ValueError): self.moves()
    def test_owned_and_started_players_excluded(self):
        self.assertEqual(self.moves(owned={'starter','bench','add'}), [])
        self.assertEqual(self.moves(now=self.now+timedelta(days=2)), [])
    def test_open_slot_needs_no_drop(self):
        self.roster['players'] = ['starter']
        self.assertIsNone(self.moves()[0]['drop'])
    def test_reserve_player_not_drop_candidate(self):
        self.roster['reserve'] = ['bench']
        # IR creates room in this fixture, so any recommendation uses the open slot.
        self.assertTrue(all(m['drop'] is None for m in self.moves()))
    def test_failure_keeps_report_available(self):
        with patch('recommendations.read_url', side_effect=OSError('unavailable')):
            text = recommendation_section({'season':2026}, {}, set(), {}, {'week':1}, self.now)
        self.assertIn('Comparisons unavailable', text)
        self.assertIn('scouting report remains available', text)

if __name__ == '__main__': unittest.main()

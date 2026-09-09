import unittest
from bridge import holdings, find_roster, drops_since, scouting, render
from datetime import datetime, timezone


class BridgeTests(unittest.TestCase):
    def test_all_roster_holdings_and_nulls(self):
        self.assertEqual(holdings({'players': ['1'], 'reserve': ['2'], 'taxi': ['3']}), {'1', '2', '3'})
        self.assertEqual(holdings({'players': None}), set())

    def test_identity_and_ambiguous_owner(self):
        roster = {'owner_id': 'other', 'co_owners': ['me']}
        self.assertEqual(find_roster([roster], 'me'), roster)
        with self.assertRaises(ValueError):
            find_roster([], 'me')
        with self.assertRaises(ValueError):
            find_roster([roster, roster], 'me')

    def test_completed_drops_dedup_and_reclaimed(self):
        tx = {'transaction_id': 't', 'type': 'waiver', 'status': 'complete', 'status_updated': 200, 'drops': {'a': 1, 'b': 2}}
        self.assertEqual(len(drops_since([tx, tx], 100, {'b'})), 1)
        self.assertEqual(drops_since([tx], 201, set()), [])
        self.assertEqual(drops_since([{**tx, 'status': 'failed'}], 100, set()), [])
        self.assertEqual(drops_since([{**tx, 'type': 'trade'}], 100, set()), [])

    def test_week_boundary_timestamps(self):
        tx = lambda ident, stamp: {'transaction_id': ident, 'type': 'free_agent', 'status': 'complete', 'status_updated': stamp, 'drops': {ident: 1}}
        self.assertEqual([r['player_id'] for r in drops_since([tx('oldweek', 150), tx('newweek', 250)], 100, set())], ['newweek', 'oldweek'])

    def test_watchlist_needs_and_ownership(self):
        players = {'a': {'position': 'RB'}, 'b': {'position': 'WR'}, 'c': {'position': 'RB'}, 'k': {'position': 'K'}}
        trend = [{'player_id': p, 'count': n} for p, n in [('a', 5), ('b', 100), ('c', 500), ('k', 1000)]]
        result = scouting(trend, {'c'}, {'starters': ['0', 'b'], 'players': ['b']}, players, ['RB', 'WR', 'BN'])
        self.assertEqual([r['player_id'] for r in result], ['a', 'b'])
        self.assertTrue(result[0]['gap'])

    def test_report_discloses_limitations_and_empty_results(self):
        result = render({'name': 'League', 'season': '2026', 'roster_positions': ['QB']}, {'roster_id': 7, 'starters': ['0']}, {}, [], [], datetime.now(timezone.utc), 0)
        self.assertIn('No completed drops', result)
        self.assertIn('No projections', result)
        self.assertIn('Empty', result)


if __name__ == '__main__':
    unittest.main()

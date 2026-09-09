import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import bridge

class ReportIntegrationTests(unittest.TestCase):
    def test_preview_and_checkpoint_with_mock_api(self):
        league = {'name': 'Test league', 'sport': 'nfl', 'season': '2026', 'roster_positions': ['RB', 'BN'], 'settings': {'leg': 1}}
        roster = {'owner_id': '326127889974034432', 'roster_id': 7, 'players': ['a'], 'starters': ['0']}
        calls = []
        def fake_get(path):
            calls.append(path)
            if path == '/state/nfl': return {'season': '2026', 'week': 1}
            if path.endswith('/rosters'): return [roster]
            if '/transactions/' in path: return []
            if path == '/players/nfl': return {'a': {'full_name': 'Owned Player', 'position': 'RB'}, 'b': {'full_name': 'Available Player', 'position': 'RB'}}
            if '/trending/' in path: return [{'player_id': 'a', 'count': 100}, {'player_id': 'b', 'count': 5}]
            return league
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            try:
                os.chdir(temp)
                with patch('recommendations.read_url', side_effect=OSError('offline fixture')), patch('bridge.get', side_effect=fake_get), patch.dict(os.environ, {'REPORT_TIMEZONE': 'UTC'}), patch('sys.argv', ['bridge.py', '--preview']):
                    bridge.main()
                self.assertFalse(Path('data/state.json').exists())
                self.assertIn('Available Player', Path('reports/latest.md').read_text())
                self.assertIn('/league/1388592505368363009/transactions/0', calls)
                self.assertIn('/league/1388592505368363009/transactions/1', calls)
                with patch('recommendations.read_url', side_effect=OSError('offline fixture')), patch('bridge.get', side_effect=fake_get), patch.dict(os.environ, {'REPORT_TIMEZONE': 'UTC'}), patch('sys.argv', ['bridge.py']):
                    bridge.main()
                before = Path('data/state.json').read_text()
                with patch('bridge.get', side_effect=RuntimeError('API unavailable')), patch.dict(os.environ, {'REPORT_TIMEZONE': 'UTC'}), patch('sys.argv', ['bridge.py']):
                    with self.assertRaises(RuntimeError): bridge.main()
                self.assertEqual(before, Path('data/state.json').read_text())
            finally:
                os.chdir(previous)

import unittest
from report_formats import email_html, pdf_bytes, headline, blocks, inline

SAMPLE = '''# The 40 year dash: daily Sleeper report
Generated: 2026-09-10T06:00:00-04:00
Season: 2026 | Roster: 7 | Reception points: 0.5
## Your roster
| Slot | Player | Position | Team | Injury status |
|---|---|---|---|---|
| QB | Josh Allen | QB | BUF | None reported |
## Projection-based add/drop comparisons
**Hold your roster:** no move clears the thresholds.
## Dropped players still unrostered
No completed drops remain unrostered.
## Roster-specific watchlist
- **Example player** (RB): 50 adds.
'''

class FormatTests(unittest.TestCase):
    def test_html_and_pdf_preserve_content(self):
        rendered = email_html(SAMPLE)
        self.assertIn('Josh Allen', rendered)
        self.assertIn('<th ', rendered)
        self.assertIn('Hold your roster', rendered)
        self.assertNotIn('|---|', rendered)
        self.assertTrue(pdf_bytes(SAMPLE).startswith(b'%PDF-'))
    def test_untrusted_markup_escaped(self):
        self.assertNotIn('<script>', email_html(SAMPLE + '\n<script>alert(1)</script>'))
        self.assertNotIn('href=', inline('[bad](javascript:alert)'))
    def test_unavailable_is_not_hold(self):
        self.assertEqual(headline({'Projection-based add/drop comparisons':['**Comparisons unavailable:** missing']} )[0], 'Scouting report ready')

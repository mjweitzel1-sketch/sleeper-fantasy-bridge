import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from notify import deliver

class NotificationTests(unittest.TestCase):
    def test_send_once_and_persist_only_after_success(self):
        env = {key: 'example' for key in ('SMTP_HOST', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'EMAIL_FROM', 'EMAIL_TO')}
        env['EMAIL_FROM'] = 'sender@example.com'
        env['EMAIL_TO'] = 'recipient@example.com'
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, env), patch('notify.smtplib.SMTP') as smtp:
            report, ledger = Path(tmp) / 'report.md', Path(tmp) / 'ledger.json'
            report.write_text('# League\nGenerated: 2026-09-09T06:00:00-04:00\nReport')
            smtp.return_value.__enter__.return_value.send_message.side_effect = RuntimeError('failed')
            with self.assertRaises(RuntimeError):
                deliver(report, ledger)
            self.assertFalse(ledger.exists())
            smtp.return_value.__enter__.return_value.send_message.side_effect = None
            deliver(report, ledger)
            deliver(report, ledger)
            self.assertEqual(smtp.return_value.__enter__.return_value.send_message.call_count, 2)

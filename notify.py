"""Optional SMTP email delivery; invoked only after explicit configuration."""
import hashlib
import json
import os
from pathlib import Path
import smtplib
import ssl
from email.message import EmailMessage
from bridge import write_json


def deliver(report_path='reports/latest.md', ledger_path='data/delivery.json'):
    required = ('SMTP_HOST', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'EMAIL_FROM', 'EMAIL_TO')
    if any(not os.getenv(key) for key in required):
        raise ValueError('Email requires SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO secrets')
    report = Path(report_path).read_text(encoding='utf-8')
    # A stable date/league/recipient key prevents normal same-day reruns sending twice.
    generated = next(line for line in report.splitlines() if line.startswith('Generated: '))
    key = hashlib.sha256((report.splitlines()[0] + generated[11:21] + os.environ['EMAIL_TO']).encode()).hexdigest()
    ledger_file = Path(ledger_path)
    ledger = json.loads(ledger_file.read_text()) if ledger_file.exists() else {}
    if key in ledger:
        print('Email already sent for this report date.')
        return
    message = EmailMessage()
    message['Subject'] = 'Your daily Sleeper report'
    message['From'] = os.environ['EMAIL_FROM']
    message['To'] = os.environ['EMAIL_TO']
    message['Message-ID'] = f'<{key}@sleeper-fantasy-bridge.local>'
    from report_formats import email_html, pdf_bytes
    message.set_content(report)
    message.add_alternative(email_html(report), subtype='html')
    date = generated[11:21]
    message.add_attachment(pdf_bytes(report), maintype='application', subtype='pdf',
                           filename=f'sleeper-report-{date}.pdf')
    with smtplib.SMTP(os.environ['SMTP_HOST'], int(os.getenv('SMTP_PORT', '587')), timeout=30) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(os.environ['SMTP_USERNAME'], os.environ['SMTP_PASSWORD'])
        smtp.send_message(message)
    ledger[key] = generated
    write_json(ledger_file, ledger)
    print('Email sent.')


if __name__ == '__main__':
    deliver()

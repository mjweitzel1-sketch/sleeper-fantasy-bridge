"""Presentation layer: readable Gmail HTML and a matching downloadable PDF."""
import html
import io
import re
from pathlib import Path
from urllib.parse import urlsplit

NAVY = '#142D46'
TEAL = '#167B73'


def parse_report(markdown):
    title = 'Sleeper daily report'
    metadata, sections = [], {}
    current = None
    for line in markdown.splitlines():
        if line.startswith('# '):
            title = line[2:]
        elif line.startswith('## '):
            current = line[3:]
            sections[current] = []
        elif current is None:
            if line.strip(): metadata.append(line.strip())
        else:
            sections[current].append(line)
    projection = sections.get('Projection-based add/drop comparisons', [])
    notes = [line for line in projection if line.startswith(('Guards:', 'Season totals are', '[Free projection endpoint]'))]
    if notes:
        sections['Projection-based add/drop comparisons'] = [line for line in projection if line not in notes]
        sections['Methodology and sources'] = notes
    return title, metadata, sections


def inline(text):
    text = html.escape(text.strip(), quote=True)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    def link(match):
        label, url = match.groups()
        if urlsplit(html.unescape(url)).scheme != 'https':
            return label
        return f'<a href="{url}">{label}</a>'
    return re.sub(r'\[([^\]]+)\]\(([^\s)]+)\)', link, text)


def blocks(lines):
    """Parse the small Markdown subset emitted by bridge.py without executing HTML."""
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', c) for c in cells): rows.append(cells)
                i += 1
            yield 'table', rows
            continue
        yield ('bullet' if line.startswith('- ') else 'paragraph'), line[2:] if line.startswith('- ') else line
        i += 1


def ordered(sections):
    preferred = ['Projection-based add/drop comparisons', 'Your roster', 'Dropped players still unrostered', 'Roster-specific watchlist', 'Limits and next action']
    return [k for k in preferred if k in sections] + [k for k in sections if k not in preferred]


def headline(sections):
    text = '\n'.join(sections.get('Projection-based add/drop comparisons', []))
    if '**Comparisons unavailable:**' in text:
        return 'Scouting report ready', 'Projection comparisons are unavailable today. Review the details below.'
    if '**Hold your roster:**' in text:
        return 'Hold your roster', 'No available swap cleared the improvement thresholds today.'
    if '- Add **' in text:
        return 'Pickup opportunities', 'Review the alternatives below before making a move in Sleeper.'
    return 'Your daily league briefing', 'Roster, recent drops, and available trending players in one place.'


def email_html(markdown):
    title, metadata, sections = parse_report(markdown)
    heading, summary = headline(sections)
    parts = ['<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>',
             '<body style="margin:0;background:#eef3f6;font-family:Arial,Helvetica,sans-serif;color:#23384b">',
             '<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:20px 10px">',
             '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:680px;background:#fff;border:1px solid #dce5eb">',
             f'<tr><td style="padding:28px;background:{NAVY};color:#fff"><div style="font-size:11px;letter-spacing:2px;color:#9bd7ce">SLEEPER / DAILY BRIEF</div>',
             f'<h1 style="font-size:25px;margin:12px 0">{html.escape(heading)}</h1><p style="font-size:15px;line-height:1.5;margin:0">{html.escape(summary)}</p></td></tr>',
             '<tr><td style="padding:24px">', f'<p style="font-size:13px;color:#5c7080;margin:0 0 8px">{html.escape(title)}</p>',
             ''.join(f'<p style="font-size:12px;color:#5c7080;margin:4px 0">{inline(m)}</p>' for m in metadata),
             '<p style="padding:12px;background:#edf7f4;font-size:13px;line-height:1.5">The complete report is attached as a PDF. Download it from this email to save or print.</p>']
    for name in ordered(sections):
        parts.append(f'<h2 style="font-size:18px;color:{NAVY};margin:28px 0 12px;border-bottom:2px solid #dceae6;padding-bottom:9px">{html.escape(name)}</h2>')
        for kind, value in blocks(sections[name]):
            if kind == 'table':
                parts.append('<table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;font-size:12px;line-height:1.4">')
                for r, row in enumerate(value):
                    parts.append('<tr>')
                    for cell in row:
                        color = '#fff' if r == 0 else '#23384b'
                        bg = NAVY if r == 0 else ('#f2f6f8' if r % 2 else '#fff')
                        tag = 'th' if r == 0 else 'td'
                        parts.append(f'<{tag} align="left" style="padding:9px 6px;color:{color};background:{bg};border-bottom:1px solid #e3eaee;vertical-align:top">{inline(cell)}</{tag}>')
                    parts.append('</tr>')
                parts.append('</table>')
            else:
                prefix = '&#8226; ' if kind == 'bullet' else ''
                parts.append(f'<p style="font-size:14px;line-height:1.55;margin:9px 0">{prefix}{inline(value)}</p>')
    parts.append('<p style="margin-top:28px;padding-top:14px;border-top:1px solid #dce5eb;font-size:11px;color:#617586">Read-only recommendations. Check current news, waiver eligibility, and claim timing in Sleeper before acting.</p></td></tr></table></td></tr></table></body></html>')
    return ''.join(parts)


def pdf_bytes(markdown):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    title, metadata, sections = parse_report(markdown)
    heading, summary = headline(sections)
    output = io.BytesIO()
    width = letter[0] - 88
    body = ParagraphStyle('body', fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor('#23384b'), spaceAfter=6)
    small = ParagraphStyle('small', parent=body, fontSize=8, leading=11, textColor=colors.HexColor('#5c7080'))
    h1 = ParagraphStyle('hero', parent=body, fontName='Helvetica-Bold', fontSize=25, leading=29, textColor=colors.HexColor(NAVY), spaceAfter=10)
    h2 = ParagraphStyle('section', parent=body, fontName='Helvetica-Bold', fontSize=13, leading=17, spaceBefore=14, spaceAfter=9, keepWithNext=True)
    cell = ParagraphStyle('cell', parent=body, fontSize=8.5, leading=11, spaceAfter=0)
    header = ParagraphStyle('header', parent=cell, fontName='Helvetica-Bold', textColor=colors.white)
    story = [Paragraph('SLEEPER / DAILY BRIEF', small), Spacer(1,8), Paragraph(html.escape(heading), h1), Paragraph(html.escape(summary), body),
             Paragraph(html.escape(title), small)]
    story += [Paragraph(inline(m), small) for m in metadata]
    story.append(Spacer(1,10))
    for name in ordered(sections):
        if name == 'Dropped players still unrostered':
            story.append(PageBreak())
        story.append(Paragraph(html.escape(name), h2))
        for kind, value in blocks(sections[name]):
            if kind == 'table':
                cells = [[Paragraph(inline(c), header if i == 0 else cell) for c in row] for i, row in enumerate(value)]
                widths = [width / len(value[0])] * len(value[0])
                # Widths sum to the available letter-page content area.
                if len(value[0]) == 5: widths = [45,166,53,47,width-311]
                table = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
                table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(NAVY)),
                    ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f2f6f8'),colors.white]),
                    ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
                    ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
                    ('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor(TEAL))]))
                story += [table, Spacer(1,8)]
            else:
                text = inline(value)
                if kind == 'bullet': text = '&#8226; ' + text
                story.append(Paragraph(text, body))
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#d7e2e9'))
        canvas.line(44,35,letter[0]-44,35)
        canvas.setFont('Helvetica',8)
        canvas.setFillColor(colors.HexColor('#5c7080'))
        canvas.drawString(44,23,'THE 40 YEAR DASH  /  Scouting, not automatic roster changes')
        canvas.drawRightString(letter[0]-44,23,f'{doc.page}')
        canvas.restoreState()
    SimpleDocTemplate(output,pagesize=letter,rightMargin=44,leftMargin=44,topMargin=38,bottomMargin=48,
                      title=title,author='Sleeper Fantasy Bridge').build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()


def export_report(markdown_path):
    path = Path(markdown_path)
    text = path.read_text(encoding='utf-8')
    path.with_suffix('.html').write_text(email_html(text),encoding='utf-8')
    path.with_suffix('.pdf').write_bytes(pdf_bytes(text))

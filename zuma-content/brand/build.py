#!/usr/bin/env python3
"""Assemble the ZUMA brand playbook page: template + logo symbols + generated tables."""
import html, pathlib, re

HERE = pathlib.Path(__file__).parent
logo = (HERE / 'logo-defs.svg').read_text()
tpl = (HERE / 'template.html').read_text()

AREAS = [
    ('Metabolic', '#A3CEFF', '#1F4FD8', '#0B1F5C', 'RT-3 · TZ-2 · MOTS-c · NAD+'),
    ('Tissue', '#ABE9C3', '#0E9A5B', '#0A3B26', 'BPC+TB'),
    ('Dermal', '#FFB7C5', '#FF5A1F', '#9E1717', 'GHK-Cu · KLOW'),
    ('Endocrine', '#FFE97A', '#D08000', '#5E3C00', 'Tesamorelin · CJC+IPA'),
    ('Neuro', '#D9C8FF', '#6E3FD8', '#2A1263', 'Selank · Semax'),
    ('Lab supplies', '#D9E1EA', '#4E6077', '#1B2533', 'BAC water'),
]

def strip(areas):
    out = []
    for name, lt, br, dp, _ in areas:
        out.append(f'<div class="tri" aria-hidden="true"><i style="background:{lt}"></i>'
                   f'<i style="background:{br}"><b>{html.escape(name)}</b></i><i style="background:{dp}"></i></div>')
    return '\n'.join(out)

def swatches(areas):
    out = []
    for name, lt, br, dp, items in areas:
        out.append(f'''<figure class="sw">
  <div class="sw-b" style="background:{lt};color:{dp}"><span>Light</span><code>{lt}</code></div>
  <div class="sw-b" style="background:{br};color:#fff"><strong>{html.escape(name.upper())}</strong><code>{br}</code></div>
  <div class="sw-b" style="background:{dp};color:#fff"><span>Deep</span><code>{dp}</code></div>
  <figcaption>{html.escape(items)}</figcaption>
</figure>''')
    return '\n'.join(out)

# (compound, area colour, fill, mg or None, now, proposed)
PRICES = [
    ('RT-3', '#1F4FD8', '10 mg', 10, 129, 99),
    ('RT-3', '#1F4FD8', '20 mg', 20, 219, 169),
    ('TZ-2', '#1F4FD8', '15 mg', 15, 139, 109),
    ('TZ-2', '#1F4FD8', '30 mg', 30, 249, 169),
    ('MOTS-c', '#1F4FD8', '10 mg', 10, 69, 59),
    ('MOTS-c', '#1F4FD8', '40 mg', 40, 189, 159),
    ('NAD+', '#1F4FD8', '500 mg', 500, 79, 69),
    ('NAD+', '#1F4FD8', '1000 mg', 1000, 139, 109),
    ('BPC+TB', '#0E9A5B', '10 mg', 10, 89, 79),
    ('BPC+TB', '#0E9A5B', '20 mg', 20, 159, 129),
    ('GHK-Cu', '#FF5A1F', '50 mg', 50, 49, 45),
    ('GHK-Cu', '#FF5A1F', '100 mg', 100, 84, 69),
    ('KLOW', '#FF5A1F', 'fill to confirm', None, None, 129),
    ('Tesamorelin', '#D08000', '10 mg', 10, 129, 79),
    ('CJC+IPA', '#D08000', '10 mg', 10, 99, 79),
    ('Selank', '#6E3FD8', '10 mg', 10, 69, 54),
    ('Semax', '#6E3FD8', '10 mg', 10, 69, 49),
    ('BAC water', '#4E6077', '10 mL', None, 19, 12),
]

def price_rows():
    out = []
    for name, col, fill, mg, now, new in PRICES:
        per = f'${new / mg:,.2f}' if mg else '—'
        nowc = f'${now}' if now else 'new'
        chg = f'−{round((now - new) / now * 100)}%' if now else '—'
        out.append(f'<tr><th scope="row"><span class="dot" style="background:{col}"></span>{name}</th>'
                   f'<td>{fill}</td><td class="num">{nowc}</td><td class="num strong">${new}</td>'
                   f'<td class="num">{per}</td><td class="num">{chg}</td></tr>')
    return '\n'.join(out)

page = (tpl.replace('{{LOGO}}', logo)
           .replace('{{STRIP}}', strip(AREAS))
           .replace('{{SWATCHES}}', swatches(AREAS))
           .replace('{{PRICES}}', price_rows()))

# Never-words lint on the reader-facing text, outside the one list that names them.
text = re.sub(r'<svg.*?</svg>', ' ', page, flags=re.S)
text = re.sub(r'<style>.*?</style>|<script>.*?</script>', ' ', text, flags=re.S)
text = re.sub(r'<ul class="words never".*?</ul>', ' ', text, flags=re.S)
text = re.sub(r'<del class="bad">.*?</del>', ' ', text, flags=re.S)
text = re.sub(r'<[^>]+>', ' ', text).lower()
NEVER = ['dose', 'dosing', 'cycle', 'stack', 'results', 'gains', 'recovery', 'benefits', 'heal', 'treat',
         'safe', 'clinically proven', 'pharmaceutical grade', 'for human use', 'before and after',
         'performance', 'weight loss', 'muscle']
hits = [w for w in NEVER if re.search(r'\b' + re.escape(w) + r'\b', text)]
if hits:
    raise SystemExit(f'never-words found: {hits}')

(HERE / 'zuma-playbook.html').write_text(page)
print('ok', len(page))

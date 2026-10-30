# ZUMA launch email: "The new era of research is here."
# Table-based, 600 px, inline styles, web-safe fonts with Outfit where the client loads it.
#   python3 build_email.py -> launch-email.html (absolute image URLs, for sending)
#                             launch-email-preview.html (local images, for checking)
#                             launch-email.txt (plain-text part)
import os
HERE = os.path.dirname(os.path.abspath(__file__))
SEND_BASE = 'https://zumatides.com/email/launch/'      # upload img/ here before sending
SITE = 'https://zumatides.com'
CODE = 'LAUNCH10'
UTM = '?utm_source=email&utm_medium=blast&utm_campaign=launch'
OX, SNOW, STUCCO, INK, MUTED = '#6E1C2A', '#FCFBF8', '#EFE4D2', '#1A1012', '#6B5B57'
AREA = {'metabolic': '#1F4FD0', 'tissue': '#0E9A58', 'dermal': '#FF5A1F', 'endocrine': '#D08000', 'neuro': '#6E3FD8', 'supplies': '#4E6077'}
PRODUCTS = [  # name, size, launch price from, area, page slug (KLOW -> shop until its page lands)
    ('RT-3', '10 mg', 89, 'metabolic', 'rt-3'), ('TZ-2', '15 mg', 139, 'metabolic', 'tz-2'), ('MOTS-c', '10 mg', 69, 'metabolic', 'mots-c'),
    ('NAD+', '500 mg', 79, 'metabolic', 'nad-plus'), ('BPC+TB', '10 mg', 89, 'tissue', 'bpc-tb'), ('GHK-Cu', '50 mg', 49, 'dermal', 'ghk-cu'),
    ('KLOW', '80 mg', 139, 'dermal', 'shop'), ('TESAMORELIN', '10 mg', 129, 'endocrine', 'tesamorelin'), ('CJC+IPA', '10 mg', 99, 'endocrine', 'cjc-ipa'),
    ('SELANK', '10 mg', 69, 'neuro', 'selank'), ('SEMAX', '10 mg', 69, 'neuro', 'semax'), ('BAC WATER', '10 mL', 19, 'supplies', 'bac-water')]
SANS = "'Helvetica Neue',Helvetica,Arial,sans-serif"
HEAD = "'Outfit','Helvetica Neue',Helvetica,Arial,sans-serif"
MONO = "'Courier New',Courier,monospace"

def build(base):
    img = lambda f: base + f
    def btn(label, href, bg=OX, fg=SNOW):
        return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td bgcolor="{bg}" style="border-radius:999px">'
                f'<a href="{href}" style="display:inline-block;padding:15px 30px;font-family:{SANS};font-size:15px;font-weight:700;color:{fg};'
                f'text-decoration:none;border-radius:999px;letter-spacing:.02em">{label}</a></td></tr></table>')
    def tile(p):
        name, size, price, area, slug = p; c = AREA[area]
        fs = 15 if len(name) > 8 else 19
        return (f'<td class="tile" width="33%" valign="top" style="padding:4px">'
                f'<a href="{SITE}/{slug}.html{UTM}" style="text-decoration:none;display:block">'
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td class="tcell" bgcolor="{c}" style="padding:16px 14px 14px;height:88px" valign="bottom">'
                f'<div class="tarea" style="font-family:{MONO};font-size:10px;letter-spacing:.12em;color:{SNOW};opacity:.85;text-transform:uppercase">{area if area != "supplies" else "lab supplies"}</div>'
                f'<div class="tname" style="font-family:{HEAD};font-size:{fs}px;font-weight:800;color:{SNOW};line-height:1.15;margin-top:4px">{name}</div>'
                f'<div class="tmeta" style="font-family:{MONO};font-size:12px;color:{SNOW};margin-top:4px">{size.upper()} · from ${price}</div>'
                f'</td></tr></table></a></td>')
    rows = ''.join('<tr>' + ''.join(tile(p) for p in PRODUCTS[i:i + 3]) + '</tr>' for i in range(0, 12, 3))
    def pillar(k, title, body):
        return (f'<tr><td style="padding:0 40px 26px" class="px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
                f'<td width="44" valign="top" style="font-family:{MONO};font-size:13px;color:{OX};font-weight:700;padding-top:3px">{k}</td>'
                f'<td valign="top"><div style="font-family:{HEAD};font-size:19px;font-weight:800;color:{INK}">{title}</div>'
                f'<div style="font-family:{SANS};font-size:15px;line-height:1.55;color:{MUTED};margin-top:5px">{body}</div></td></tr></table></td></tr>')
    pre = 'Twelve research compounds. Every lot tested. Launch pricing is live, and your first order takes another 10% off.'
    return f'''<!doctype html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">
<title>The new era of research is here.</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@700;800&display=swap" rel="stylesheet">
<style>
body{{margin:0;padding:0;background:{STUCCO}}} a{{color:{OX}}} img{{border:0;display:block;outline:none;text-decoration:none}}
@media (max-width:620px){{ .wrap{{width:100%!important}} .px{{padding-left:22px!important;padding-right:22px!important}}
 .h1{{font-size:40px!important;line-height:1.02!important}} .tile{{padding:3px!important}} .tcell{{padding:12px 8px 10px!important;height:70px!important}} .tarea{{display:none!important}} .tname{{font-size:13px!important}} .tmeta{{font-size:10px!important}} }}
</style></head>
<body style="margin:0;padding:0;background:{STUCCO}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{STUCCO}">{pre}&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{STUCCO}"><tr><td align="center" style="padding:24px 10px">
<table role="presentation" class="wrap" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:600px;background:{SNOW}">

<tr><td bgcolor="{OX}" style="padding:34px 40px 30px" class="px">
  <img src="{img('zuma-snow.png')}" width="150" alt="ZUMA" style="width:150px;height:auto">
  <div style="font-family:{MONO};font-size:11px;letter-spacing:.2em;color:#E9D3D7;margin-top:14px">RESEARCH COMPOUNDS · NOW OPEN</div>
</td></tr>

<tr><td style="padding:46px 40px 10px" class="px">
  <div class="h1" style="font-family:{HEAD};font-size:52px;font-weight:800;line-height:1.0;color:{INK};letter-spacing:-.02em">The new era of research is&nbsp;here.</div>
  <div style="font-family:{SANS};font-size:17px;line-height:1.55;color:{MUTED};margin-top:20px">Twelve research compounds, built the way a lab supplier should have been built all along: every lot tested, every report published, every vial packed like it matters. ZUMA is open.</div>
  <div style="margin-top:28px">{btn('Enter the store', SITE + '/shop.html' + UTM)}</div>
</td></tr>

<tr><td style="padding:34px 0 0"><a href="{SITE}/shop.html{UTM}"><img src="{img('collection.jpg')}" width="600" alt="ZUMA vials: RT-3, TZ-2, Tesamorelin, GHK-Cu, MOTS-c, BPC+TB" style="width:100%;max-width:600px;height:auto"></a></td></tr>

<tr><td bgcolor="{OX}" style="padding:30px 40px" class="px">
  <div style="font-family:{MONO};font-size:11px;letter-spacing:.2em;color:#E9D3D7">LAUNCH OFFER</div>
  <div style="font-family:{HEAD};font-size:30px;font-weight:800;line-height:1.12;color:{SNOW};margin-top:10px">Launch pricing is live: 20% under list.<br>Your first order takes another 10%&nbsp;off.</div>
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-top:20px"><tr>
    <td style="border:2px dashed #E9D3D7;padding:12px 22px;font-family:{MONO};font-size:22px;font-weight:700;letter-spacing:.18em;color:{SNOW}">{CODE}</td>
  </tr></table>
  <div style="font-family:{SANS};font-size:13px;color:#E9D3D7;margin-top:12px">Enter the code at checkout. One use per researcher.</div>
  <div style="margin-top:22px">{btn('Claim launch pricing', SITE + '/shop.html' + UTM, SNOW, OX)}</div>
</td></tr>

<tr><td style="padding:40px 36px 10px" class="px">
  <div style="font-family:{MONO};font-size:11px;letter-spacing:.2em;color:{OX};padding:0 4px">THE LINEUP · 12 COMPOUNDS · 6 RESEARCH AREAS</div>
</td></tr>
<tr><td style="padding:6px 36px 34px" class="px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table></td></tr>

<tr><td style="padding:10px 40px 24px" class="px"><div style="font-family:{HEAD};font-size:30px;font-weight:800;color:{INK};line-height:1.1">What makes it a new&nbsp;era</div></td></tr>
{pillar('01', 'Tested, then published.', 'Every lot is tested by HPLC and mass spec before it ships, and the report goes up at zumatides.com/lots. Scan the QR on any box to see the report for your lot.')}
{pillar('02', 'Packed like it matters.', 'Each vial sits in its own printed carton in its research-area colour, the inside flooded in that colour, shipped in a padded mailer.')}
{pillar('03', 'Built for researchers.', 'Build a set of three or more and save up to 15%. Free shipping over $250. USDC checkout. Every order earns points toward Fellow and Principal tiers.')}

<tr><td style="padding:6px 0 0"><img src="{img('plainB-open.jpg')}" width="600" alt="An open ZUMA carton, blue inside, with the vial in a white insert" style="width:100%;max-width:600px;height:auto"></td></tr>

<tr><td align="center" style="padding:40px 40px 44px" class="px">
  <div style="font-family:{HEAD};font-size:26px;font-weight:800;color:{INK};line-height:1.15">The bench is set.</div>
  <div style="font-family:{SANS};font-size:15px;color:{MUTED};margin:10px 0 24px">Code {CODE} takes 10% off your first order.</div>
  {btn('Shop ZUMA', SITE + '/shop.html' + UTM)}
</td></tr>

<tr><td bgcolor="{INK}" style="padding:30px 40px" class="px">
  <img src="{img('zuma-snow.png')}" width="84" alt="ZUMA" style="width:84px;height:auto;opacity:.9">
  <div style="font-family:{SANS};font-size:12px;line-height:1.6;color:#BFB2AE;margin-top:16px"><b style="color:{SNOW}">For laboratory research use only. Not for human or veterinary use.</b> Products are sold to qualified researchers for in-vitro and laboratory study. No statement here is medical advice or a claim of any effect in humans or animals.</div>
  <div style="font-family:{SANS};font-size:12px;line-height:1.6;color:#BFB2AE;margin-top:14px">You are receiving this because you joined the ZUMA list. ZUMA · {{{{ADDRESS}}}}<br>
  <a href="{{{{{{RESEND_UNSUBSCRIBE_URL}}}}}}" style="color:{SNOW}">Unsubscribe</a> · <a href="{SITE}{UTM}" style="color:{SNOW}">zumatides.com</a></div>
</td></tr>

</table></td></tr></table></body></html>'''

TEXT = f'''The new era of research is here.

Twelve research compounds, built the way a lab supplier should have been built all along: every lot tested, every report published, every vial packed like it matters. ZUMA is open.

LAUNCH OFFER
Launch pricing is live: 20% under list.
Your first order takes another 10% off with code {CODE}.
Shop: {SITE}/shop.html{UTM}

THE LINEUP
''' + '\n'.join(f'- {n} {s}, from ${p}' for n, s, p, a, sl in PRODUCTS) + f'''

WHAT MAKES IT A NEW ERA
01 Tested, then published. Every lot is tested by HPLC and mass spec before it ships; the report goes up at zumatides.com/lots. Scan the QR on any box for your lot.
02 Packed like it matters. Each vial ships in its own printed carton in its research-area colour, in a padded mailer.
03 Built for researchers. Sets of three or more save up to 15%. Free shipping over $250. USDC checkout. Points toward Fellow and Principal tiers.

The bench is set. {SITE}/shop.html{UTM}

For laboratory research use only. Not for human or veterinary use.
ZUMA · {{{{ADDRESS}}}}
Unsubscribe: {{{{{{RESEND_UNSUBSCRIBE_URL}}}}}}
'''

if __name__ == '__main__':
    open(os.path.join(HERE, 'launch-email.html'), 'w').write(build(SEND_BASE))
    open(os.path.join(HERE, 'launch-email-preview.html'), 'w').write(build('img/'))
    open(os.path.join(HERE, 'launch-email.txt'), 'w').write(TEXT)
    print('ok')

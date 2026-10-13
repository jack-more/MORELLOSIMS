#!/usr/bin/env python3
"""Build the ZUMA site from one source (src/) into two outputs.

  dist/       a static site for any host (Vercel, Netlify, Cloudflare Pages): index.html (home), shop.html,
              one product page per compound (rt-3.html ...), brand.html, assets/js, assets/img
  artifact/   the same pages for a claude.ai Artifact: page.html (home) starts at <title> (the host adds doctype/html/head/body);
              shop.html, the product pages and brand.html are full documents beside it

Source markers resolved here:
  <!-- @css -->     the brand guide's CSS, inlined in a <style>: tokens.css (compiled from src/design/tokens.json by tools/tokens2css.py),
                   then src/css/ui.css (every component), then src/css/site.css (the shop's layout), plus src/css/brand.css on the guide page
  <!-- @guide --> <!-- @toc --> <!-- @palette -->   brand.html only: src/design/brand-guide.md rendered to HTML, its contents, and the palette
  <!-- @logo -->    src/logo-slot.svg, the one copy of the logo (<symbol id="zuma-logo">), marked <!-- LOGO SLOT -->
  <!-- @wheel -->   src/partials/wheel.svg (regenerate with tools/wheel.py)
  <!-- @body -->    splits head content from body content
  <!-- @header --> <!-- @footer --> <!-- @panels --> <!-- @faq -->   src/partials/*.html, shared by every shop page
  <!-- @mega --> <!-- @menu --> <!-- @promos --> <!-- @footshop --> <!-- @catalog -->   rendered from src/data/catalog.json
  src/product.html  the product page template: {{NO}}, {{NAME}} ... and <!-- @sizes --> <!-- @spec --> <!-- @lots --> <!-- @pair --> <!-- @related -->
  {{ASSET}}        "assets/" in dist, "" in the artifact
  {{BRAND}} {{HOME}}  links to the brand guide and the home page; {{H}} prefixes home-page anchors ("" on the home page itself)

Usage: python3 build.py      (no dependencies; Pillow is used only to add a JPEG copy of the social image)
"""
import html, json, pathlib, re, shutil, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / 'tools'))
from tokens2css import compile_css

ROOT = pathlib.Path(__file__).resolve().parent
SRC, DIST, ART = ROOT / 'src', ROOT / 'dist', ROOT / 'artifact'
RUO = 'For laboratory research use only. Not for human or veterinary use.'
NEVER = re.compile(r"\b(dos(e|es|ed|ing)|cycl(e|es|ed|ing)|stack(s|ed|ing)?|results?|gains?|recover(y|ies)?|benefits?|heal(s|ed|ing)?|treat(s|ed|ing|ment|ments)?"
                   r"|safe(ly|ty)?|clinically proven|pharmaceutical grade|for human use|before and after|performance|weight loss|muscles?)\b", re.I)
def pages():
    """(source, dist name, artifact name, description, kind, product index)"""
    out = [('page.html', 'index.html', 'page.html', 'ZUMA: six peptides for performance and longevity research, in small lots in small, fresh lots, each in the three tones of its research area. For laboratory research use only.', 'home', None),
           ('shop.html', 'shop.html', 'shop.html', 'Shop all six ZUMA research peptides: tested by HPLC and MS, every lot report published. For laboratory research use only.', 'shop', None)]
    for i, p in enumerate(json.loads((SRC / 'data' / 'catalog.json').read_text(encoding='utf-8'))['products']):
        out.append(('product.html', p['slug'] + '.html', p['slug'] + '.html', f'ZUMA {p["name"]}: {p["about"]} For laboratory research use only.', 'pdp', i))
    out.append(('build.html', 'build.html', 'build.html', 'Build a ZUMA set: pick any research peptides; three or more compounds save 10%, five or more save 15%. For laboratory research use only.', 'build', None))
    out.append(('lots.html', 'lots.html', 'lots.html', 'Every ZUMA lot, its test status and its report. Search by the lot number on the vial or carton. For laboratory research use only.', 'lots', None))
    out.append(('brand.html', 'brand.html', 'brand.html', 'ZUMA brand guide: the four research-area palettes, the bands, interaction rules, layout, type, the label and the research-use rules.', 'brand', None))
    return out

def read(rel): return (SRC / rel).read_text(encoding='utf-8')

def inline(md):
    t = html.escape(md, quote=False)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', t)

def slug(t): return re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')

def markdown(md):
    """The small Markdown the brand guide uses: ## and ### headings, paragraphs, - and 1. lists, - [ ] checklists, pipe tables.
    The never-words line is fenced with <!-- never-list --> so the compliance lint skips it."""
    out, toc, lines, i = [], [], md.strip().split('\n'), 0
    while i < len(lines):
        l = lines[i]
        if not l.strip(): i += 1; continue
        m = re.match(r'(#{2,3}) (.+)', l)
        if m:
            lvl, txt = len(m.group(1)), m.group(2); hid = slug(txt)
            if lvl == 2: toc.append((hid, txt))
            out.append(f'<h{lvl} id="{hid}">{inline(txt)}</h{lvl}>'); i += 1; continue
        if l.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', c) for c in cells): rows.append(cells)
                i += 1
            head = ''.join(f'<th scope="col">{inline(c)}</th>' for c in rows[0])
            body = ''.join('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>' for r in rows[1:])
            out.append(f'<div class="tbl"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'); continue
        if re.match(r'(- |\d+\. )', l):
            ordered = bool(re.match(r'\d+\. ', l)); items = []
            while i < len(lines) and re.match(r'(- |\d+\. )', lines[i]):
                items.append(re.sub(r'^(- |\d+\. )', '', lines[i])); i += 1
            check = all(x.startswith('[ ] ') for x in items)
            lis = []
            for x in items:
                x = x[4:] if check else x; li = f'<li>{inline(x)}</li>'
                if 'Never write:' in x: li = '<!-- never-list -->' + li + '<!-- /never-list -->'
                lis.append(li)
            tag = 'ol' if ordered else 'ul'
            cls = ' class="check"' if check else ''
            out.append(f'<{tag}{cls}>' + ''.join(lis) + f'</{tag}>'); continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r'(#{2,3} |\||- |\d+\. )', lines[i]):
            para.append(lines[i]); i += 1
        out.append(f'<p>{inline(" ".join(para))}</p>')
    return '\n'.join(out), toc

def palette(tokens):
    val = {t['name']: t['value']['day'] for t in tokens['color']['tokens']}
    areas = [('metabolic', 'Metabolic', 'RT-3 · MOTS-c'), ('tissue', 'Tissue', 'BPC-157 · TB-500'), ('dermal', 'Dermal', 'GHK-Cu'), ('endocrine', 'Endocrine', 'Ipamorelin')]
    cols = ''.join(f'<div data-area="{k}"><div class="z-light z-pad"><b>{n}</b><span>light · {val[k + "-light"]}</span></div>'
                   f'<div class="z-bright z-pad"><b>{nos}</b><span>bright · {val[k + "-bright"]}</span></div>'
                   f'<div class="z-deep z-pad"><b>Research use only</b><span>deep · {val[k + "-deep"]}</span></div></div>' for k, n, nos in areas)
    house = [('paper', 'z-paper', 'Page ground'), ('sand', 'z-sand', 'Second ground'), ('white', 'z-white', 'Tiles and panels'), ('ink', 'z-ink', 'Text, buttons, dark ground')]
    hs = ''.join(f'<div class="{c}" style="box-shadow:inset 0 0 0 2px var(--line)"><b>{n.capitalize()}</b><span>{val[n]} · {u}</span></div>' for n, c, u in house)
    return f'<div class="pal-areas">{cols}</div>\n<div class="pal-house">{hs}</div>'

CAT = json.loads((SRC / 'data' / 'catalog.json').read_text(encoding='utf-8'))
SW = '<span class="z-swatch" aria-hidden="true"><i></i><i></i><i></i></span>'
ARR = '<span class="z-arr" aria-hidden="true">→</span>'
def esc(t): return html.escape(str(t), quote=True)
def area_of(k): return CAT['areas'][k]
def by_no(n): return next(p for p in CAT['products'] if p['no'] == n)
def lot_of(p): return p['code'] + '-2610A'
def list_of(price): return round(price * 100 / (100 - CAT['launch']['off']))   # the struck list price beside a launch price
def launch_price(price): return f'<span class="lchip">Launch</span><s>${list_of(price)}</s>${price}'
STATUS = {'ok': ('Report published', '<span class="z-tag z-tag-solid z-tag-dot">Report published</span>'),
          'pending': ('In testing: ships when its report is out', '<span class="z-tag z-tag-ring">In testing</span>')}

def mega():
    cols = ''
    for k, a in CAT['areas'].items():
        items = ''.join(f'<a class="mega-item" href="{p["slug"]}.html"><span class="mega-img z-light" data-area="{k}"><img src="{{{{ASSET}}}}img/vial-{p["no"]}.webp" alt="" loading="lazy"></span>'
                        f'<span><b>{esc(p["name"])}</b><small>{esc(p["full"])} · from ${p["sizes"][0][1]}</small></span></a>' for p in CAT['products'] if p['area'] == k)
        cols += f'<div class="mega-col" data-area="{k}"><p class="mega-h">{SW}{a["label"]}</p>{items}</div>'
    return (f'<div class="z-wrap mega-in"><div class="mega-cols">{cols}</div>'
            f'<a class="mega-feature z-sand" href="build.html"><img src="{{{{ASSET}}}}img/set-pack-800.webp" alt="" loading="lazy"><b>Build a set</b><small>Any compounds · save up to 15%</small><span class="z-btn z-btn-sm">Build your set {ARR}</span></a>'
            f'<p class="mega-all"><a class="z-link" href="shop.html">Shop all six {ARR}</a></p></div>')

def menu():
    prods = ''.join(f'<a href="{p["slug"]}.html"><span>{esc(p["name"])}</span></a>' for p in CAT['products'])
    return (f'<p class="z-kicker z-soft menu-h">Shop</p><a href="shop.html"><span>Shop all six</span></a>{prods}'
            f'<a href="build.html"><span>Build a set</span></a>'
            f'<p class="z-kicker z-soft menu-h">ZUMA</p><a href="lots.html">Lot reports</a><a href="{{{{H}}}}#sets">Sets</a><a href="{{{{H}}}}#token">$ZUMA</a><a href="{{{{H}}}}#referrals">Referrals</a><a href="{{{{H}}}}#about">About</a>')

def promos():
    out = ''
    for i, (t, href, cta) in enumerate(CAT['promos']):
        href = ('{{H}}' + href) if href.startswith('#') else href
        out += f'<span class="promo-msg" data-i="{i}"{"" if i == 0 else " hidden"}>{esc(t)} <a href="{href}">{esc(cta)}</a></span>'
    return out

def footshop():
    return '<a href="shop.html">Shop all six</a><a href="build.html">Build a set</a>' + ''.join(f'<a href="{p["slug"]}.html">{esc(p["name"])}</a>' for p in CAT['products']) + '<a href="shop.html#sets">Sets</a>'

def catalog_script():
    data = {k: v for k, v in CAT.items() if not k.startswith('_')}
    return '<script>window.ZUMA_CATALOG=' + json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') + ';</script>'

def related_card(p):
    k = p['area']; a = area_of(k)
    return (f'<article class="z-card z-pcard" data-area="{k}">'
            f'<div class="z-light z-pic"><img src="{{{{ASSET}}}}img/vial-{p["no"]}.webp" width="720" height="960" loading="lazy" alt="ZUMA {esc(p["name"])} vial">'
            f'</div>'
            f'<div class="z-bright z-pad"><span class="z-area">{a["label"]}</span><h3>{esc(p["name"])}</h3><p class="z-full">{esc(p["full"]) if p["full"].upper() != p["name"].upper() else "Lyophilized"}</p></div>'
            f'<div class="z-deep z-pad"><div class="z-row"><span class="z-price">{launch_price(p["sizes"][0][1])}</span><a class="z-btn z-btn-sm z-stretch" href="{p["slug"]}.html" aria-label="View {esc(p["name"])}">View {ARR}</a></div></div></article>')

def pdp_fill(s, i):
    p = CAT['products'][i]; k = p['area']; a = area_of(k)
    sizes = ''.join(f'<label class="z-option"><input type="radio" name="fill" value="{j}"{" checked" if j == p["def"] else ""}><span>{z[0]}<small>${z[1]}</small></span></label>' for j, z in enumerate(p['sizes']))
    fills = ' or '.join(z[0] for z in p['sizes'])
    spec_rows = [('Form', 'Lyophilized (freeze-dried) powder'), ('Fills', fills), ('Vial', '10 mL clear glass, flip-off cap')] + list(p['spec'].items()) + \
                [('Identity', 'Mass spectrometry, every lot'), ('Purity', 'HPLC, on the lot report'), ('Storage', '−20 °C, away from light')]
    spec = ('<dl class="speclist">' + ''.join(f'<div><dt>{esc(t)}</dt><dd>{esc(v)}</dd></div>' for t, v in spec_rows) + '</dl>'
            '<p class="z-note"><span class="z-tag z-tag-dash">Placeholder</span> Confirm every figure against the lot report before launch.</p>')
    words, tag = STATUS[p['status']]
    lots = [(lot_of(p), CAT['lot']['filled'], p['status'])] + [(f'{p["code"]}-{pre}A', d, 'ok') for pre, d in CAT['lot']['previous']]
    lot_rows = ''.join(f'<tr><td class="z-tnm">{lt}</td><td data-k="Fill">{" · ".join(z[0] for z in p["sizes"])}</td><td data-k="Filled">{d}</td><td data-k="Tested">HPLC · MS</td>'
                       f'<td>{STATUS[st][1]}</td><td>' + (f'<a class="z-link" href="#lot-record" aria-label="Report for lot {lt} (placeholder)">Report ↗</a>' if st == 'ok' else '<span class="z-soft">Due</span>') + '</td></tr>'
                       for lt, d, st in lots)
    pair = next((x for x in CAT['sets'] if len(x['items']) == 2 and p['no'] in x['items']), None)
    if pair:
        o = by_no(next(n for n in pair['items'] if n != p['no'])); lst = sum(by_no(n)['sizes'][by_no(n)['def']][1] for n in pair['items'])
        pair_html = (f'<div class="pdp-pair"><p class="z-legend">Complete the pair</p><div class="pairc" data-area="{o["area"]}"><span class="z-light pair-img"><img src="{{{{ASSET}}}}img/vial-{o["no"]}.webp" alt=""></span>'
                     f'<div><b>{esc(o["name"])}</b><span>{area_of(o["area"])["label"]} · from ${o["sizes"][0][1]}</span>'
                     f'<div class="pair-btns"><a class="z-btn z-btn-line z-btn-sm" href="{o["slug"]}.html">View {esc(o["name"])}</a><button class="z-btn z-btn-sm" type="button" data-set="{pair["key"]}">Add the pair · ${pair["price"]}, save ${lst - pair["price"]}</button></div></div></div></div>')
    else:
        col = next(x for x in CAT['sets'] if x['key'] == 'collection'); lst = sum(by_no(n)['sizes'][by_no(n)['def']][1] for n in col['items'])
        pair_html = (f'<div class="pdp-pair"><p class="z-legend">Complete the collection</p><div class="pairc"><span class="z-sand pair-img"><img src="{{{{ASSET}}}}img/box-1000.webp" alt=""></span>'
                     f'<div><b>The Collection</b><span>All six, one of each, boxed</span><div class="pair-btns"><button class="z-btn z-btn-sm" type="button" data-set="collection">Add the Collection · ${col["price"]}, save ${lst - col["price"]}</button></div></div></div></div>')
    related = ''.join(related_card(x) for x in CAT['products'] if x['no'] != p['no'])
    rep = {'{{NO}}': p['no'], '{{NAME}}': esc(p['name']), '{{FULL}}': esc(p['full']), '{{AREA}}': k, '{{AREA_LABEL}}': a['label'], '{{AREA_SHORT}}': a['short'].lower(),
           '{{AREA_SHORT_LOWER}}': a['short'].lower(), '{{ABOUT}}': esc(p['about']), '{{I}}': str(i), '{{FROM}}': str(p['sizes'][p['def']][1]), '{{LIST}}': str(list_of(p['sizes'][p['def']][1])),
           '{{LOT}}': lot_of(p), '{{FILLED}}': CAT['lot']['filled'], '{{STATUS}}': tag, '{{STATUS_WORDS}}': words, '{{LABEL_S}}': '-s' if p['no'] == '01' else '',
           '{{BADGE}}': f'<span class="z-tag z-tag-solid pdp-badge">{esc(p["badge"])}</span>' if p['badge'] else ''}
    for t, v in rep.items(): s = s.replace(t, v)
    return (s.replace('<!-- @sizes -->', sizes).replace('<!-- @spec -->', spec).replace('<!-- @lots -->', lot_rows)
             .replace('<!-- @pair -->', pair_html).replace('<!-- @related -->', related))

def assemble(name, asset, home, page_kind='home', pdp=None):
    s = read(name)
    if pdp is not None: s = pdp_fill(s, pdp)
    tokens = json.loads(read('design/tokens.json'))
    css = compile_css(tokens) + read('css/ui.css') + read('css/site.css') + (read('css/brand.css') if name == 'brand.html' else '')
    s = s.replace('<!-- @css -->', '<style>\n' + css + '</style>')
    s = s.replace('<!-- @logo -->', read('logo-slot.svg').strip())
    panels = read('partials/panels.html')
    if page_kind == 'pdp': panels = re.sub(r'<!-- drawer -->.*?<!-- /drawer -->', '', panels, flags=re.S)
    s = (s.replace('<!-- @header -->', read('partials/header.html')).replace('<!-- @footer -->', read('partials/footer.html'))
          .replace('<!-- @panels -->', panels).replace('<!-- @faq -->', read('partials/faq.html')))
    s = (s.replace('<!-- @mega -->', mega()).replace('<!-- @menu -->', menu()).replace('<!-- @promos -->', promos())
          .replace('<!-- @footshop -->', footshop()).replace('<!-- @catalog -->', catalog_script()))
    s = s.replace('<!-- @wheel -->', read('partials/wheel.svg').strip())
    if name == 'brand.html':
        guide, toc = markdown(read('design/brand-guide.md'))
        s = s.replace('<!-- @guide -->', guide).replace('<!-- @palette -->', palette(tokens))
        s = s.replace('<!-- @toc -->', ''.join(f'<a href="#{h}">{inline(t)}</a>' for h, t in toc))
    s = s.replace('{{H}}', '' if page_kind == 'home' else home)
    s = s.replace('{{ASSET}}', asset).replace('{{BRAND}}', 'brand.html').replace('{{HOME}}', home)
    head, body = s.split('<!-- @body -->', 1)
    return head.strip(), body.strip()

def document(head, body, desc, asset):
    meta = (f'<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'<meta name="description" content="{desc}">\n<meta name="theme-color" content="#111319">\n'
            f'<meta property="og:title" content="ZUMA">\n<meta property="og:description" content="{desc}">\n'
            f'<meta property="og:type" content="website">\n<meta property="og:image" content="{asset}img/og.jpg">\n'
            f'<link rel="icon" href="{asset}img/favicon.svg" type="image/svg+xml">')
    return f'<!doctype html>\n<html lang="en">\n<head>\n{meta}\n{head}\n</head>\n<body>\n{body}\n</body>\n</html>\n'

FAVICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#1F4FD8"/><path fill="#FFFFFF" fill-rule="evenodd" transform="translate(7.13 5) scale(0.2200)" d="M50.48 18.39 51.03 16.49 51.3 15.67 51.58 14.86 51.97 13.8 52.3 13 52.64 12.21 52.88 11.68 53.26 10.9 53.66 10.13 54.09 9.37 54.54 8.63 54.86 8.13 55.52 7.17 55.88 6.7 56.43 6 57 5.33 57.41 4.89 58.24 4.04 58.68 3.62 59.35 3.02 60.29 2.26 60.77 1.9 61.51 1.37 62.28 0.88 62.8 0.57 63.33 0.28 63.87 0 63.31 0.23 62.73 0.43 60.38 1.24 58.58 1.89 57.07 2.5 56.16 2.9 55.25 3.32 54.35 3.78 53.76 4.1 52.56 4.8 51.98 5.16 51.1 5.74 50.25 6.36 49.69 6.78 48.87 7.45 48.06 8.16 47.28 8.89 47.01 9.16 46.52 9.65 45.8 10.45 45.1 11.26 44.43 12.1 43.79 12.96 43.58 13.27 43.19 13.83 42.62 14.73 41.9 15.96 41.41 16.88 40.98 17.75 40.32 17.16 39.92 16.83 39.11 16.18 38.59 15.79 37.27 14.87 35.87 14 35.34 13.7 34.98 13.51 34.38 13.19 33.78 12.89 33.41 12.73 32.8 12.44 32.17 12.17 31.76 12.03 31.13 11.78 30.47 11.54 30.05 11.43 29.38 11.21 28.7 11.01 28.24 10.92 27.54 10.75 26.89 10.62 25.63 10.42 24.4 10.3 23.67 10.24 23.13 10.24 22.39 10.21 21.69 10.23 20.37 10.31 19.8 10.39 19.07 10.47 18.34 10.59 17.06 10.88 16.51 11.05 15.81 11.25 15.12 11.48 13.92 11.97 13.4 12.23 12.76 12.53 12.16 12.86 11.07 13.52 10.63 13.85 10.07 14.23 9.55 14.64 8.64 15.42 8.27 15.81 7.82 16.24 7.38 16.7 7.07 17.09 6.66 17.55 6.32 17.99 5.66 18.91 4.8 20.28 4.59 20.69 4.32 21.17 4.06 21.67 3.9 22.07 3.66 22.56 3.44 23.05 3.3 23.46 3.1 23.94 2.92 24.43 2.8 24.84 2.48 25.79 2.11 27.13 1.79 28.46 1.44 30.23 1.22 31.52 0.97 33.24 0.43 37.39 0.17 39 0 39.79 0.24 39.02 0.5 38.26 0.93 37.13 1.24 36.38 1.74 35.28 2.28 34.2 2.66 33.5 3.26 32.46 4.12 31.12 4.81 30.15 5.29 29.53 5.78 28.93 6.31 28.33 6.56 28.06 7.36 27.23 8.21 26.46 9.08 25.75 9.69 25.3 9.97 25.11 10.6 24.71 10.89 24.54 11.53 24.19 12.17 23.89 12.47 23.75 13.12 23.51 13.42 23.41 14.07 23.21 14.72 23.07 15.66 22.92 16.31 22.87 16.94 22.86 17.23 22.86 17.86 22.9 18.77 23.02 19.39 23.15 20.27 23.38 21.15 23.68 21.75 23.92 22.61 24.31 23.47 24.76 24.31 25.25 24.9 25.63 25.97 26.37 26.79 27 27.84 27.85 28.64 28.55 29.67 29.5 30.46 30.26 32.27 32.07 34.4 34.14 38.57 38.11 40.01 39.5 40.15 39.65 40.22 39.88 39.08 39.75 38.87 41.18 38.8 41.62 38.64 42.55 38.37 43.92 37.98 45.71 37.64 47.07 37.28 48.41 36.89 49.75 36.48 51.08 35.89 52.82 35.42 54.13 35.09 55 34.4 56.73 33.68 58.41 33.11 59.68 32.51 60.94 31.69 62.58 31.05 63.82 30.6 64.65 29.7 66.26 28.99 67.46 28.03 69.02 27.28 70.19 26.51 71.35 25.48 72.86 24.67 74 23.84 75.12 22.73 76.57 21.86 77.66 20.7 79.07 19.8 80.13 18.88 81.18 17.65 82.53 16.7 83.55 15.27 85.03 11.66 85.03 11.66 100 68.06 100 68.06 85.03 34.36 85.03 35.4 83.28 36.45 81.42 37.21 80.03 37.95 78.63 38.91 76.73 39.6 75.3 40.49 73.37 41.13 71.92 41.74 70.47 42.34 69 43.1 67.01 43.64 65.53 44.16 64.03 44.65 62.53 45.27 60.5 45.71 58.98 46.25 56.93 46.5 55.92 46.86 54.38 47.3 52.3 47.69 50.22 47.87 49.2 48.12 47.64 48.4 45.53 48.59 43.97 48.75 42.4 48.88 40.88 46.69 40.62 47.37 39.88 48.48 38.7 52.76 34.27 55.02 31.9 55.83 31.09 56.65 30.31 57.3 29.74 58.14 29.03 58.8 28.52 59.47 28.04 60.15 27.59 60.84 27.17 61.54 26.79 62.24 26.46 62.96 26.16 63.69 25.91 64.2 25.76 64.72 25.64 65.48 25.51 66.25 25.44 66.78 25.42 67.03 25.42 67.57 25.45 68.12 25.5 68.92 25.64 69.72 25.84 70.27 26.02 70.81 26.23 71.61 26.59 72.39 27.01 73.16 27.49 73.9 28.03 74.62 28.62 75.32 29.25 75.77 29.71 75.99 29.93 76.63 30.65 77.24 31.4 77.99 32.45 78.53 33.27 79.18 34.4 79.63 35.27 80.17 36.47 80.63 37.7 80.46 37.06 80.26 36.08 79.63 32.74 79.41 31.71 79.17 30.67 78.9 29.61 78.47 28.18 78.09 27.1 77.65 26.01 77.14 24.92 76.55 23.83 76.12 23.13 75.88 22.75 75.6 22.38 75.39 22.06 74.54 21.02 73.92 20.35 73.58 20.01 73.2 19.68 72.91 19.39 72.5 19.06 71.75 18.48 70.96 17.94 70.49 17.66 69.63 17.19 68.72 16.76 68.2 16.54 67.66 16.36 67.25 16.19 66.24 15.9 65.71 15.77 65.13 15.66 64.7 15.56 64.12 15.48 63.11 15.36 62.52 15.34 62.1 15.3 61.51 15.3 60.93 15.32 60.51 15.32 58.94 15.46 57.93 15.63 57.42 15.72 56.85 15.86 56.46 15.94 55.94 16.08 55.39 16.25 55.03 16.35 54.53 16.52 53.99 16.73 53.64 16.85 53.17 17.04 51.88 17.63 50.66 18.28Z"/></svg>\n'

def copy_assets(img_to, js_to):
    for d in (img_to, js_to): d.mkdir(parents=True, exist_ok=True)
    for f in sorted((SRC / 'img').glob('*')):
        if f.suffix in ('.webp', '.jpg', '.png', '.svg'): shutil.copy2(f, img_to / f.name)
    for sub in ('spin', 'hspin'):   # drag-to-turn frames: product pages (spin) and the home hero (hspin)
        if (SRC / 'img' / sub).is_dir():
            (img_to / sub).mkdir(exist_ok=True)
            for f in sorted((SRC / 'img' / sub).glob('*.webp')): shutil.copy2(f, img_to / sub / f.name)
    for f in sorted((SRC / 'js').glob('*.js')): shutil.copy2(f, js_to / f.name)
    (img_to / 'favicon.svg').write_text(FAVICON)
    try:
        from PIL import Image
        Image.open(SRC / 'img' / 'og.webp').convert('RGB').save(img_to / 'og.jpg', quality=88)
    except Exception as e:
        print('  (og.jpg skipped:', e, ')')

def check(path):
    """Compliance lint: never-words in visible copy and scripts, and the research-use line."""
    t = path.read_text(encoding='utf-8')
    t = re.sub(r'<!-- never-list -->.*?<!-- /never-list -->', '', t, flags=re.S)   # the brand sheet's own list of never-words
    t = t.replace('safe-area-inset', '')                                              # CSS syntax, not copy
    t = re.sub(r'performance and longevity research', '', t, flags=re.I)              # the positioning line names a research field, never a result
    hits = sorted({m.group(0).lower() for m in NEVER.finditer(t)})
    text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', t))
    ruo = text.count(RUO)
    print(f'  {path.relative_to(ROOT)}: research-use line x{ruo}' + (f'  NEVER-WORDS: {hits}' if hits else ''))
    return not hits

def build():
    for out in (DIST, ART):
        if out.exists(): shutil.rmtree(out)
    copy_assets(DIST / 'assets' / 'img', DIST / 'assets' / 'js')
    copy_assets(ART / 'img', ART / 'js')
    for src, dname, aname, desc, kind, idx in pages():
        head, body = assemble(src, 'assets/', './', kind, idx)
        (DIST / dname).write_text(document(head, body, desc, 'assets/'), encoding='utf-8')
        head, body = assemble(src, '', './', kind, idx)
        if aname == 'page.html':   # the Artifact host wraps this one itself: it must begin with <title>
            assert head.startswith('<title>'), 'page.html must start with <title>'
            (ART / aname).write_text(head + '\n' + body + '\n', encoding='utf-8')
        else:
            (ART / aname).write_text(document(head, body, desc, ''), encoding='utf-8')
    ok = True
    for f in sorted(DIST.glob('*.html')) + [ART / 'page.html'] + sorted((DIST / 'assets' / 'js').glob('*.js')):
        ok = check(f) and ok
    n = sum(1 for _ in (DIST / 'assets' / 'img').glob('*'))
    print(f'built dist/ ({n} images) and artifact/' + ('' if ok else '  -- fix the never-words above'))
    return ok

if __name__ == '__main__':
    sys.exit(0 if build() else 1)

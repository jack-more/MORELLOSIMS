#!/usr/bin/env python3
"""Compile the brand guide's tokens.json into tokens.css, laid out the way the design system page compiles it:
:root colours (aliases as var()), :root spacing / radius / shadow / other families, --font-<family>, and one class per type style.
Usage: python3 tokens2css.py path/to/tokens.json > tokens.css"""
import json, re, sys

def compile_css(tokens):
    theme = tokens['color']['themes'][0]['id']
    val = lambda t: t['value'] if isinstance(t['value'], str) else t['value'].get(theme)
    css_val = lambda v: re.sub(r'^\{(.+)\}$', r'var(--\1)', v) if isinstance(v, str) else v
    out = [f'/* ZUMA — generated from tokens.json */', f':root, [data-theme="{theme}"] {{']
    out += [f'  --{t["name"]}: {css_val(val(t))};' for t in tokens['color']['tokens']]
    out += [f'  --{t["name"]}: {css_val(val(t))};' for t in tokens.get('shadow', {}).get('tokens', [])]
    out.append('}')
    out.append(':root {')
    for fam, body in tokens.items():
        if fam in ('name', 'version', 'color', 'type', 'shadow', 'meta') or not isinstance(body, dict) or 'tokens' not in body: continue
        out += [f'  --{t["name"]}: {t["value"]};' for t in body['tokens']]
    out += [f'  --font-{k}: {v};' for k, v in tokens['type']['families'].items()]
    out.append('}')
    px = lambda v: f'{v}px' if isinstance(v, (int, float)) and not isinstance(v, bool) else v
    for g in tokens['type']['groups']:
        for s in g['styles']:
            fam = s.get('family', g['family'])
            decl = [f'font-family: var(--font-{fam})', f'font-size: {px(s["fontSize"])}', f'line-height: {s["lineHeight"]}', f'font-weight: {s["fontWeight"]}']
            if 'letterSpacing' in s: decl.append(f'letter-spacing: {s["letterSpacing"]}')
            out.append(f'.{s["name"]} {{ ' + '; '.join(decl) + '; }')
    return '\n'.join(out) + '\n'

if __name__ == '__main__':
    sys.stdout.write(compile_css(json.load(open(sys.argv[1]))))

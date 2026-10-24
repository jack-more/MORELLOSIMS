#!/usr/bin/env python3
"""One set of icons and link-preview tags for every page.

The current brand (Oct 2026): PFP B (green asterisk, blue M) for the icons and
the banknote banner X uses for the preview image. Pages and page builders call
apply(); run it on files to rewrite their <head> in place:

  python3 scripts/brand_head.py index.html members/index.html ...

apply() drops the page's own icon links, og:image / twitter image tags and
og:site_name, and writes the shared block after </title>. og:title,
og:description and og:url stay when the page has them, and are filled from
<title>, the meta description and the file's path when it doesn't.
"""

import html as _html
import os
import re
import sys

SITE = "https://morellosims.com"
OG_IMAGE = f"{SITE}/assets/brand/og-2627.jpg"     # assets/brand/og-2627.jpg, 1200x630
ICONS = ('<link rel="icon" href="/assets/brand/v2/mark.svg" type="image/svg+xml">\n'
         '<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">\n'
         '<link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180">')
DROP = [r'<link[^>]*rel="(?:shortcut )?icon"[^>]*>', r'<link[^>]*rel="apple-touch-icon[^"]*"[^>]*>',
        r'<meta[^>]*property="og:(?:image|image:width|image:height|image:alt|site_name)"[^>]*>',
        r'<meta[^>]*name="twitter:(?:card|image|image:alt)"[^>]*>']


def _meta(html, attr, name):
    m = re.search(rf'<meta[^>]*{attr}="{re.escape(name)}"[^>]*content="([^"]*)"', html)
    return m.group(1) if m else None


def apply(html, url=None):
    """html with the shared icons and preview tags. url: the page's public URL, used for og:url."""
    if "</title>" not in html:
        return html
    for rx in DROP:
        html = re.sub(r"[ \t]*" + rx + r"[ \t]*\n?", "", html)
    title = re.search(r"<title>([^<]*)</title>", html).group(1).strip()
    lines = [ICONS, '<meta property="og:site_name" content="Morello Sims">']
    if not _meta(html, "property", "og:type"):
        lines.append('<meta property="og:type" content="website">')
    if url and not _meta(html, "property", "og:url"):
        lines.append(f'<meta property="og:url" content="{url}">')
    if not _meta(html, "property", "og:title"):
        lines.append(f'<meta property="og:title" content="{title}">')
    desc = _meta(html, "name", "description")
    if desc and not _meta(html, "property", "og:description"):
        lines.append(f'<meta property="og:description" content="{desc}">')
    lines += [f'<meta property="og:image" content="{OG_IMAGE}">',
              '<meta property="og:image:width" content="1200">',
              '<meta property="og:image:height" content="630">',
              f'<meta property="og:image:alt" content="{_html.escape("Morello Sims: NBA picks from a simulation, every pick graded in public")}">',
              '<meta name="twitter:card" content="summary_large_image">',
              f'<meta name="twitter:image" content="{OG_IMAGE}">']
    return html.replace("</title>", "</title>\n" + "\n".join(lines), 1)


def url_for(path):
    rel = os.path.relpath(os.path.abspath(path), os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    rel = rel.replace(os.sep, "/")
    if rel.endswith("index.html"):
        rel = rel[: -len("index.html")]
    return f"{SITE}/{rel}"


if __name__ == "__main__":
    for p in sys.argv[1:]:
        src = open(p, encoding="utf-8").read()
        out = apply(src, url_for(p))
        if out != src:
            open(p, "w", encoding="utf-8").write(out)
            print(f"  {p}")

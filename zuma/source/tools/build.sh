#!/bin/sh
# Builds tools/render.html: the lux7 render page (lux6 kit, lux7 base and harness, the field-bands direction for reference)
# plus the site's Tricolor label (../src/js/label.js), the Tricolor direction entry (tricolor.js) and the page's logo slot,
# so the stills read the logo from the same <symbol id="zuma-logo"> as the site.
cd "$(dirname "$0")"
L=../../lux7
{ printf '<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="%s"><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>' "$(cat $L/fonts.txt)"
  printf '<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.min.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"}}</script></head><body style="margin:0">\n'
  cat ../src/logo-slot.svg
  printf '<script>\n'
  cat ../../lab/glyphs.js ../../lab/prints.js ../../lux6/unb.js ../../lux6/lib.js $L/base.js $L/parts-core.js $L/dirs-r3.js ../src/js/label.js tricolor.js $L/harness7.js
  printf '</script><script type="module">\n'; cat scene.js; printf '</script></body></html>'; } > render.html

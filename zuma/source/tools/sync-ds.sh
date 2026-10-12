#!/bin/sh
# Mirror the site's design sources into the brand guide (the ZUMA Design System artifact's files, staged in ../../zds/project).
# The site is the source: src/design/tokens.json, src/design/brand-guide.md and src/css/ui.css.
cd "$(dirname "$0")/.."
D=../zds/project
cp src/design/tokens.json $D/tokens.json
cp src/design/brand-guide.md $D/README.md
cp src/css/ui.css $D/components/bundle.css
echo "synced tokens.json, README.md, components/bundle.css -> $D"

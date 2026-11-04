const { chromium } = require('playwright'); const fs = require('fs'), path = require('path');
(async () => { const b = await chromium.launch(); const p = await b.newPage(); const dir = process.argv[2];
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.svg'))) {
    const svg = fs.readFileSync(path.join(dir, f), 'utf8');
    await p.setContent(`<!doctype html><html><head><style>@page{size:106mm 156mm;margin:0}html,body{margin:0;padding:0}svg{display:block}</style></head><body>${svg}</body></html>`);
    await p.pdf({ path: path.join(dir, f.replace('.svg', '.pdf')), width: '106mm', height: '156mm', printBackground: true, pageRanges: '1' }); console.log('pdf', f); }
  await b.close(); })();

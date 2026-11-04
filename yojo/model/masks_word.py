# egg deboss mask for any product word: YOJO wordmark over WORD, word fitted to <= 42 mm wide
import sys
word, slug = sys.argv[1], sys.argv[2]
d=open('../yojo-wordmark-trace.txt').read().split('\n'); vb=list(map(float,d[0].split())); WM=d[1]
PX=20; W,H=120*PX,92*PX
def zy(z): return (92-z)*PX
s=27.0*PX/vb[2]; cx=W/2; cyw=zy(36.0)
wm=f'<path d="{WM}" fill="#fff" fill-rule="evenodd" transform="translate({cx-(vb[0]+vb[2]/2)*s:.2f} {cyw-(vb[1]+vb[3]/2)*s:.2f}) scale({s:.5f})"/>'
txt=f'<text id="t" x="{cx}" y="{zy(21.6)}" text-anchor="middle" font-family="Inter" font-weight="800" font-size="{9.4*PX}" letter-spacing="{0.3*PX}" fill="#fff">{word}</text>'
svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="{W}" height="{H}" fill="#000"/>{wm}{txt}</svg>'
js=f"""document.fonts.ready.then(()=>{{const t=document.getElementById('t');const w=t.getBBox().width/{PX};
if(w>42){{const f=9.4*42/w;t.setAttribute('font-size',f*{PX});t.setAttribute('letter-spacing',0.3*f/9.4*{PX});
// keep the cap line where GHK-CU sits: shift baseline up by half the size difference
t.setAttribute('y',{zy(21.6)}-(9.4-f)*{PX}*0.36);}}window.DONE=1;}})"""
open(f'w_{slug}.html','w').write(f'<html><head><style>body{{margin:0}}</style></head><body>{svg}<script>{js}</script></body></html>')

d=open('../yojo-wordmark-trace.txt').read().split('\n')
vb=list(map(float,d[0].split())); WM=d[1]
Y=['M'+s for s in WM.split('M') if s.strip()][3]
PX=20
# egg mask: x in [-60,60] mm, z in [0,92] mm
W,H=120*PX,92*PX
def zy(z): return (92-z)*PX
wm_w=27.0; s=wm_w*PX/vb[2]; cx=W/2; cyw=zy(36.0)
wm=f'<path d="{WM}" fill="#fff" fill-rule="evenodd" transform="translate({cx-(vb[0]+vb[2]/2)*s:.2f} {cyw-(vb[1]+vb[3]/2)*s:.2f}) scale({s:.5f})"/>'
txt=f'<text id="t" x="{cx}" y="{zy(21.6)}" text-anchor="middle" font-family="Inter" font-weight="800" font-size="{9.4*PX}" letter-spacing="{0.3*PX}" fill="#fff">GHK-CU</text>'
egg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="{W}" height="{H}" fill="#000"/>{wm}{txt}</svg>'
# head mask: 40x40 mm at 40px/mm
HP=40; HW=40*HP; yb=(69,70,456,420); yw=19.0; ys=yw*HP/yb[2]
yy=f'<path d="{Y}" fill="#fff" transform="translate({HW/2-(yb[0]+yb[2]/2)*ys:.2f} {HW/2-(yb[1]+yb[3]/2)*ys:.2f}) scale({ys:.5f})"/>'
head=f'<svg xmlns="http://www.w3.org/2000/svg" width="{HW}" height="{HW}"><rect width="{HW}" height="{HW}" fill="#000"/>{yy}</svg>'
for n,svg,w,h in [('egg',egg,W,H),('head',head,HW,HW)]:
    open(n+'.html','w').write(f'<html><head><style>body{{margin:0}}</style></head><body>{svg}<script>document.fonts.ready.then(()=>{{const t=document.getElementById("t");if(t)window.TW=t.getBBox().width/{PX};}})</script></body></html>')

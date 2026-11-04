import subprocess, os, sys, json, math, colorsys
import numpy as np
from PIL import Image
HERE=os.path.dirname(os.path.abspath(__file__)); PY=os.path.join(HERE,'..','bl','bin','python')
def s2l(c): c=np.asarray(c)/255.0; return np.where(c<=0.04045,c/12.92,((c+0.055)/1.055)**2.4)
def l2h(l): c=np.where(l<=0.0031308,l*12.92,1.055*np.clip(l,0,None)**(1/2.4)-0.055); return '#%02X%02X%02X'%tuple(int(round(v)) for v in np.clip(c,0,1)*255)
def hexl(h): return s2l([int(h[i:i+2],16) for i in (1,3,5)])
def black_target(palette_hex):
    r,g,b=[int(palette_hex[i:i+2],16)/255 for i in (1,3,5)]; h,s,v=colorsys.rgb_to_hsv(r,g,b)
    r,g,b=colorsys.hsv_to_rgb(h,min(1,s*1.65),v*0.91); return '#%02X%02X%02X'%(round(r*255),round(g*255),round(b*255))
def render(env,out):
    e=dict(os.environ); e.update(env)
    subprocess.run([PY,os.path.join(HERE,'mech.py')],env=e,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return np.asarray(Image.open(out).convert('RGB'),float)
def patch(a,fx=0.36,fy=0.56,f=0.03):
    H,W,_=a.shape; p=a[int(H*(fy-f)):int(H*(fy+f)),int(W*(fx-f)):int(W*(fx+f))].reshape(-1,3).mean(0); return s2l(p)
base=dict(EXPO='-0.65',STATE='locked',CLIP='0',PANEL='6',CAM_TH='-100',TEXT_TH='-90',SLOT_TH='-60',CAM_D='0.42',RX='240',RY='300',SAMPLES='12',C_EGG='600')
name,pal=sys.argv[1],sys.argv[2]; tgt=hexl(black_target(pal)); skin=tgt*0.9
for it in range(4):
    out=os.path.join(HERE,f'cm_{name}.png')
    m=patch(render(dict(base,SKIN_LIN=','.join(f'{v:.5f}' for v in skin),OUT=out),out))
    skin=np.clip(skin*tgt/np.maximum(m,1e-5),0.002,0.92)
    print(name,it,'meas',l2h(m),'target',l2h(tgt),flush=True)
json.dump({'SKIN_LIN':','.join(f'{v:.5f}' for v in skin),'target':l2h(tgt)},open(os.path.join(HERE,f'cm_{name}.json'),'w'))

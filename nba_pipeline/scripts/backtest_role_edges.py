"""Where could roles add edge? Three more checks on the 2025-26 walk-forward.

Uses scripts/backtest_roles.py's replay (fit before Feb 1, test after):
  * totals: the live total is team points for / against only. Adds each
    side's ORAPM / DRAPM x projected minutes, so an absence moves the total,
    then role coverage sums.
  * role-vs-role matchups on the spread: spacing vs the opponent's rim
    protection, creators vs rim protection, rebounding, top creator vs rim,
    each on top of RAPM talent x role-aware minutes.

2026-10-20: none beat its baseline on the test half (totals MAE 14.85 team
only vs 15.05 with player RAPM; margin 10.98 talent only vs 10.98-11.01).

Usage: python scripts/backtest_role_edges.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import scripts.backtest_roles as B  # noqa: E402
box, prior_df, pos, rapm = B.load(B.DB)
con=sqlite3.connect(B.DB)
r=pd.read_sql("select player_id, rapm_offense o, rapm_defense d from player_rapm where rapm_total is not null",con)
orapm=dict(zip(r.player_id,r.o)); drapm=dict(zip(r.player_id,r.d))
B.REPLACEMENT_RAPM=-1.0
_,go=B.replay(box,prior_df,pos,orapm); _,gd=B.replay(box,prior_df,pos,drapm)
B.REPLACEMENT_RAPM=-2.0
_,gt=B.replay(box,prior_df,pos,rapm)
g=pd.read_sql("select game_id,game_date,home_team_id h,away_team_id a,home_score hs,away_score as2 from games where season_id='2025-26' and home_score is not null order by game_date",con)
# rolling team baselines (season to date, shrunk to league avg with 10 games)
pf={};pa={};n={}; base=[]
LG=115.0
for x in g.itertuples():
    def rate(d,t): return (d.get(t,0)+10*LG)/(n.get(t,0)+10)
    base.append(dict(game_id=x.game_id, h_pf=rate(pf,x.h), h_pa=rate(pa,x.h), a_pf=rate(pf,x.a), a_pa=rate(pa,x.a),
                     total=x.hs+x.as2, margin2=x.hs-x.as2))
    for t,f_,a_ in ((x.h,x.hs,x.as2),(x.a,x.as2,x.hs)):
        pf[t]=pf.get(t,0)+f_; pa[t]=pa.get(t,0)+a_; n[t]=n.get(t,0)+1
base=pd.DataFrame(base)
df=gt.merge(base,on='game_id').merge(go[['game_id','h_str_live','a_str_live','h_str_role','a_str_role']].rename(columns=lambda c:c.replace('str','off') if 'str' in c else c),on='game_id')\
     .merge(gd[['game_id','h_str_live','a_str_live','h_str_role','a_str_role']].rename(columns=lambda c:c.replace('str','def') if 'str' in c else c),on='game_id')
tr,te=df[df.date<B.FIT_CUTOFF],df[df.date>=B.FIT_CUTOFF]
def ev(name,cols,y='total'):
    X=lambda d: np.column_stack([np.ones(len(d))]+[c(d) for c in cols])
    b=np.linalg.lstsq(X(tr),tr[y],rcond=None)[0]; e=X(te)@b-te[y]
    print(f"  {name:<52} MAE {np.abs(e).mean():.3f} RMSE {np.sqrt((e**2).mean()):.3f}")
    return X(te)@b
print("TOTALS (test",len(te),")")
team=lambda d:(d.h_pf+d.a_pa+d.a_pf+d.h_pa)/2
ev("team points for/against (like live)", [team])
for mk in ('live','role'):
    ev(f"+ player ORAPM/DRAPM x {mk} minutes", [team, lambda d,m=mk:d[f'h_off_{m}']+d[f'a_off_{m}'], lambda d,m=mk:d[f'h_def_{m}']+d[f'a_def_{m}']])
ev("+ role coverage (spacer, creator, rim, glass sums)", [team]+[lambda d,k=k:d[f'h_{k}_role']+d[f'a_{k}_role'] for k in ('spacer','creator','rim','glass')])
print("SPREAD matchups on talent residual")
talent=lambda d:d.h_str_role-d.a_str_role
pairs={'spacing vs rim protection':lambda d:d.h_spacer_role*d.a_rim_role-d.a_spacer_role*d.h_rim_role,
       'creator vs rim':lambda d:d.h_creator_role*d.a_rim_role-d.a_creator_role*d.h_rim_role,
       'glass vs glass':lambda d:d.h_glass_role-d.a_glass_role,
       'top creator vs opp rim':lambda d:d.h_top_creator_role*d.a_rim_role-d.a_top_creator_role*d.h_rim_role}
ev("talent only (margin)",[talent],'margin')
for k,f in pairs.items(): ev("talent + "+k,[talent,f],'margin')
ev("talent + all matchups",[talent]+list(pairs.values()),'margin')

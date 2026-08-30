"""Projection-free generative NFL fantasy engine v2.

The model starts from DraftKings salary/role as market priors, then simulates
team play volume, pass/rush split, player opportunity and football-stat outcomes.
It intentionally does not consume third-party fantasy projections.
"""
import numpy as np


def _shares(players, idx, kind):
    rows=players.iloc[idx]
    pos=rows.Position.astype(str).to_numpy()
    market=rows.market_score.astype(float).to_numpy()
    usage=rows.usage_multiplier.astype(float).to_numpy()
    role=rows.auto_role_multiplier.astype(float).to_numpy()
    if kind=="target":
        base=np.where(pos=="WR",1.00,np.where(pos=="TE",.72,np.where(pos=="RB",.43,.02)))
    else:
        base=np.where(pos=="RB",1.00,np.where(pos=="QB",.22,np.where(pos=="WR",.035,.015)))
    w=base*(.20+.80*market)*np.clip(usage,.25,2.25)*np.clip(role,.15,1.20)
    return w/np.maximum(w.sum(),1e-9)


def simulate_player_matrix_v2(players,n_sims=1500,seed=26):
    """Simulate DK points from football opportunity rather than point-level boom flags."""
    rng=np.random.default_rng(seed)
    n=len(players); mat=np.zeros((int(n_sims),n),dtype=np.float32)
    teams=sorted(players.Team.dropna().astype(str).unique())
    team_idx={t:np.where(players.Team.astype(str).to_numpy()==t)[0] for t in teams}
    games={}
    for t in teams:
        g=str(players.iloc[team_idx[t][0]].Game)
        games.setdefault(g,[]).append(t)

    for s in range(int(n_sims)):
        game_env={g:rng.normal(0,1) for g in games}
        team_env={t:rng.normal(0,1) for t in teams}
        team_points={}
        team_pass={}
        team_plays={}
        for g,ts in games.items():
            ge=game_env[g]
            for t in ts:
                te=team_env[t]
                # Neutral NFL environment with salary-ranked skill talent nudging efficiency.
                ids=team_idx[t]; skill=players.iloc[ids]
                talent=float(skill.loc[skill.Position.isin(["QB","RB","WR","TE"]),"market_score"].nlargest(5).mean()) if len(skill) else .5
                if not np.isfinite(talent): talent=.5
                pts=max(3.0,rng.normal(21.5+4.2*ge+3.0*te+4.0*(talent-.5),7.0))
                plays=int(np.clip(round(rng.normal(63.5+2.0*ge+1.5*te,6.0)),45,82))
                pass_rate=float(np.clip(rng.normal(.575+.025*ge, .065),.38,.76))
                team_points[t]=pts; team_plays[t]=plays; team_pass[t]=pass_rate

        for t in teams:
            ids=team_idx[t]; rows=players.iloc[ids]; pos=rows.Position.astype(str).to_numpy()
            plays=team_plays[t]; pass_att=max(12,int(round(plays*team_pass[t]))); rush_att=max(10,plays-pass_att)
            tsh=_shares(players,ids,"target"); rsh=_shares(players,ids,"rush")
            targets=rng.multinomial(pass_att,tsh); rushes=rng.multinomial(rush_att,rsh)
            # Team TD count is tied to simulated team scoring; allocation follows opportunity.
            off_td=max(0,int(round(max(0,team_points[t]-3)/7+rng.normal(0,.55))))
            td_w=.62*tsh+.38*rsh; td_w=td_w/np.maximum(td_w.sum(),1e-9)
            tds=rng.multinomial(off_td,td_w) if off_td else np.zeros(len(ids),dtype=int)
            for j,i in enumerate(ids):
                p=pos[j]; sal=float(players.iloc[i].Salary); market=float(players.iloc[i].market_score)
                if p=="DST":
                    g=str(players.iloc[i].Game); opp=[x for x in games.get(g,[]) if x!=t]
                    allowed=team_points.get(opp[0],21.5) if opp else 21.5
                    sacks=max(0,rng.poisson(2.2+.9*(1-market))); turnovers=rng.poisson(1.15)
                    pts=7.0+sacks+2*turnovers-.16*allowed+rng.normal(0,2.8)
                    mat[s,i]=max(-6,pts); continue
                if p=="QB":
                    comp=int(rng.binomial(pass_att,float(np.clip(.60+.055*market,.54,.72))))
                    ypa=float(np.clip(rng.normal(6.6+1.5*market,.85),4.5,10.5)); py=pass_att*ypa
                    pass_td=max(0,int(round(off_td*.72+rng.normal(0,.65)))); ints=rng.poisson(max(.25,1.05-.45*market))
                    ry=max(0,rushes[j]*rng.normal(5.0,1.5)); rtd=min(tds[j],2)
                    pts=.04*py+4*pass_td-ints+0.1*ry+6*rtd+(3 if py>=300 else 0)
                else:
                    catch_rate={"RB":.76,"WR":.64,"TE":.69}.get(p,.65)+.035*(market-.5)
                    rec=int(rng.binomial(int(targets[j]),float(np.clip(catch_rate,.45,.88))))
                    ypr={"RB":7.2,"WR":12.1,"TE":10.2}.get(p,9.0)*(0.78+.42*market)
                    rec_y=max(0,rec*rng.normal(ypr,2.0)); ypc={"RB":4.25,"WR":6.2,"TE":3.5}.get(p,4.2)*(0.86+.25*market)
                    rush_y=max(0,rushes[j]*rng.normal(ypc,1.0)); pts=rec+.1*(rec_y+rush_y)+6*tds[j]
                    if rec_y>=100: pts+=3
                    if rush_y>=100: pts+=3
                mat[s,i]=max(0,pts)
    return mat

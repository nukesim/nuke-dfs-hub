"""Fast projection-free generative NFL fantasy engine v2.

Static player/team arrays are prepared once, and the hot simulation loop avoids
pandas row access. The model simulates team environment -> plays -> opportunity
-> football stats -> DraftKings points.

When a sportsbook environment is supplied, current consensus team totals, game
totals, and spreads act as bounded game-context inputs. The DK salary/role model
remains the player-allocation foundation.
"""
import numpy as np
from dfs_platform import get_platform


def _norm_weights(x):
    x=np.asarray(x,dtype=float)
    s=float(x.sum())
    if s<=0:
        return np.full(len(x),1.0/max(1,len(x)))
    return x/s


def _sportsbook_inputs(environment, teams, team_game):
    """Return bounded team/game market inputs aligned to engine teams.

    Missing/non-sportsbook rows stay neutral so the historical V2 behavior is
    preserved whenever live consensus is unavailable.
    """
    nteams=len(teams)
    team_total=np.full(nteams,np.nan,dtype=float)
    game_total=np.full(nteams,np.nan,dtype=float)
    spread=np.zeros(nteams,dtype=float)
    live=np.zeros(nteams,dtype=bool)
    if environment is None or getattr(environment,"empty",True):
        return team_total,game_total,spread,live
    required={"Team","Team Total","Game Total","Spread"}
    if not required.issubset(set(environment.columns)):
        return team_total,game_total,spread,live
    for ti,t in enumerate(teams):
        m=environment[environment["Team"].astype(str).eq(str(t))]
        if "Game" in environment.columns:
            gm=m[m["Game"].astype(str).eq(str(team_game[ti]))]
            if not gm.empty: m=gm
        if "Source" in environment.columns:
            book=m[m["Source"].astype(str).eq("Sportsbook Consensus")]
            if not book.empty: m=book
            else: continue
        if m.empty: continue
        row=m.iloc[0]
        try:
            tt=float(row["Team Total"]); gt=float(row["Game Total"]); sp=float(row["Spread"])
        except Exception:
            continue
        if not (np.isfinite(tt) and np.isfinite(gt) and np.isfinite(sp)):
            continue
        team_total[ti]=np.clip(tt,12.0,38.0)
        game_total[ti]=np.clip(gt,32.0,62.0)
        spread[ti]=np.clip(sp,-14.0,14.0)
        live[ti]=True
    return team_total,game_total,spread,live


def simulate_player_matrix_v2(players,n_sims=1500,seed=26,game_environment=None,site="DK"):
    cfg=get_platform(site)
    rng=np.random.default_rng(int(seed))
    n_sims=int(n_sims); n=len(players)
    mat=np.zeros((n_sims,n),dtype=np.float32)

    pos=players.Position.astype(str).to_numpy()
    team=players.Team.astype(str).to_numpy()
    game=players.Game.astype(str).to_numpy()
    market=players.market_score.astype(float).to_numpy()
    usage=players.usage_multiplier.astype(float).to_numpy()
    role=players.auto_role_multiplier.astype(float).to_numpy()

    teams=np.array(sorted(set(team)))
    nteams=len(teams)
    team_idx=[np.where(team==t)[0] for t in teams]
    team_game=np.array([game[idx[0]] if len(idx) else "" for idx in team_idx],dtype=object)

    games=np.array(sorted(set(team_game)))
    game_to_num={g:i for i,g in enumerate(games)}
    team_game_num=np.array([game_to_num[g] for g in team_game],dtype=int)
    ngames=len(games)

    # Opponent team index for DST scoring.
    opp_team=np.full(nteams,-1,dtype=int)
    for gi in range(ngames):
        ids=np.where(team_game_num==gi)[0]
        if len(ids)>=2:
            opp_team[ids[0]]=ids[1]; opp_team[ids[1]]=ids[0]

    target_share=[]; rush_share=[]; td_share=[]; talent=[]
    for idx in team_idx:
        p=pos[idx]; m=market[idx]; u=usage[idx]; r=role[idx]
        tw=np.where(p=="WR",1.00,np.where(p=="TE",.72,np.where(p=="RB",.43,.02)))
        rw=np.where(p=="RB",1.00,np.where(p=="QB",.22,np.where(p=="WR",.035,.015)))
        tw=tw*(.20+.80*m)*np.clip(u,.25,2.25)*np.clip(r,.15,1.20)
        rw=rw*(.20+.80*m)*np.clip(u,.25,2.25)*np.clip(r,.15,1.20)
        tw=_norm_weights(tw); rw=_norm_weights(rw)
        target_share.append(tw); rush_share.append(rw); td_share.append(_norm_weights(.62*tw+.38*rw))
        skill=m[np.isin(p,["QB","RB","WR","TE"])]
        talent.append(float(np.mean(np.sort(skill)[-5:])) if len(skill) else .5)
    talent=np.nan_to_num(np.asarray(talent),nan=.5)

    # Live market context. Effects are deliberately bounded: sportsbook data
    # shapes scoring/game script but does not replace player salary/role signals.
    sb_tt,sb_gt,sb_sp,sb_live=_sportsbook_inputs(game_environment,teams,team_game)
    tt_delta=np.where(sb_live,np.clip(sb_tt-22.5,-8.0,10.0),0.0)
    gt_delta=np.where(sb_live,np.clip(sb_gt-45.0,-10.0,12.0),0.0)
    # Negative spread = favorite. Positive spread = underdog.
    script=np.where(sb_live,np.clip(sb_sp,-10.0,10.0),0.0)

    # Generate team/game environment for every universe in vectorized blocks.
    game_env=rng.normal(0,1,size=(n_sims,ngames))
    team_env=rng.normal(0,1,size=(n_sims,nteams))
    ge=game_env[:,team_game_num]

    base_points=21.5+4.2*ge+3.0*team_env+4.0*(talent[None,:]-.5)
    # Team total is the strongest market signal, but only 65% of its deviation
    # is imported so the generative model retains uncertainty/independence.
    base_points=base_points+0.65*tt_delta[None,:]
    team_points=np.maximum(3.0,rng.normal(base_points,7.0))

    # Higher-total games get a small pace/volume lift. This is intentionally
    # modest because totals mostly express scoring efficiency, not just plays.
    play_mu=63.5+2.0*ge+1.5*team_env+0.10*gt_delta[None,:]
    team_plays=np.clip(np.rint(rng.normal(play_mu,6.0)),45,82).astype(int)

    # Underdogs lean pass; favorites lean rush. High totals add a tiny passing
    # lift. Effects are capped to avoid turning spread into a projection.
    pass_mu=.575+.025*ge+0.0030*script[None,:]+0.0008*gt_delta[None,:]
    pass_rate=np.clip(rng.normal(pass_mu,.065),.38,.76)
    pass_att=np.maximum(12,np.rint(team_plays*pass_rate).astype(int))
    rush_att=np.maximum(10,team_plays-pass_att)
    off_td=np.maximum(0,np.rint(np.maximum(0,team_points-3)/7+rng.normal(0,.55,size=(n_sims,nteams))).astype(int))

    # Only loop over teams and universes for multinomial allocation. Player math is vectorized.
    for ti,idx in enumerate(team_idx):
        p=pos[idx]; m=market[idx]
        k=len(idx)
        if not k: continue
        tgt=np.empty((n_sims,k),dtype=np.int16)
        rus=np.empty((n_sims,k),dtype=np.int16)
        tds=np.zeros((n_sims,k),dtype=np.int8)
        tsh=target_share[ti]; rsh=rush_share[ti]; dsh=td_share[ti]
        for s in range(n_sims):
            tgt[s]=rng.multinomial(int(pass_att[s,ti]),tsh)
            rus[s]=rng.multinomial(int(rush_att[s,ti]),rsh)
            if off_td[s,ti]>0:
                tds[s]=rng.multinomial(int(off_td[s,ti]),dsh)

        qmask=p=="QB"; dstmask=p=="DST"; skillmask=~(qmask|dstmask)

        if np.any(skillmask):
            js=np.where(skillmask)[0]
            sp=p[js]; sm=m[js]
            rates=np.where(sp=="RB",.76,np.where(sp=="WR",.64,.69))+.035*(sm-.5)
            rates=np.clip(rates,.45,.88)
            rec=rng.binomial(tgt[:,js],rates[None,:])
            base_ypr=np.where(sp=="RB",7.2,np.where(sp=="WR",12.1,10.2))
            ypr=base_ypr*(.78+.42*sm)
            rec_y=np.maximum(0,rec*rng.normal(ypr[None,:],2.0,size=rec.shape))
            base_ypc=np.where(sp=="RB",4.25,np.where(sp=="WR",6.2,3.5))
            ypc=base_ypc*(.86+.25*sm)
            rush_y=np.maximum(0,rus[:,js]*rng.normal(ypc[None,:],1.0,size=rec.shape))
            pts=cfg.reception_points*rec+.1*(rec_y+rush_y)+6*tds[:,js]
            if cfg.yardage_bonuses: pts=pts+3*(rec_y>=100)+3*(rush_y>=100)
            mat[:,idx[js]]=np.maximum(0,pts).astype(np.float32)

        if np.any(qmask):
            for j in np.where(qmask)[0]:
                qm=m[j]; pa=pass_att[:,ti]
                ypa=np.clip(rng.normal(6.6+1.5*qm,.85,size=n_sims),4.5,10.5)
                py=pa*ypa
                pass_td=np.maximum(0,np.rint(off_td[:,ti]*.72+rng.normal(0,.65,size=n_sims)).astype(int))
                ints=rng.poisson(max(.25,1.05-.45*qm),size=n_sims)
                ry=np.maximum(0,rus[:,j]*rng.normal(5.0,1.5,size=n_sims)); rtd=np.minimum(tds[:,j],2)
                pts=.04*py+4*pass_td-ints+.1*ry+6*rtd
                if cfg.yardage_bonuses: pts=pts+3*(py>=300)
                mat[:,idx[j]]=np.maximum(0,pts).astype(np.float32)

        if np.any(dstmask):
            oi=opp_team[ti]
            allowed=team_points[:,oi] if oi>=0 else np.full(n_sims,21.5)
            for j in np.where(dstmask)[0]:
                sacks=rng.poisson(max(.2,2.2+.9*(1-m[j])),size=n_sims)
                turnovers=rng.poisson(1.15,size=n_sims)
                pts=7.0+sacks+2*turnovers-.16*allowed+rng.normal(0,2.8,size=n_sims)
                mat[:,idx[j]]=np.maximum(-6,pts).astype(np.float32)

    return mat

"""Fast projection-free generative NFL fantasy engine v2.

Static player/team arrays are prepared once, and the hot simulation loop avoids
pandas row access. The model still simulates team environment -> plays ->
opportunity -> football stats -> DraftKings points.
"""
import numpy as np


def _norm_weights(x):
    x=np.asarray(x,dtype=float)
    s=float(x.sum())
    if s<=0:
        return np.full(len(x),1.0/max(1,len(x)))
    return x/s


def simulate_player_matrix_v2(players,n_sims=1500,seed=26):
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
    team_to_num={t:i for i,t in enumerate(teams)}
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

    # Generate team/game environment for every universe in vectorized blocks.
    game_env=rng.normal(0,1,size=(n_sims,ngames))
    team_env=rng.normal(0,1,size=(n_sims,nteams))
    ge=game_env[:,team_game_num]
    team_points=np.maximum(3.0,rng.normal(21.5+4.2*ge+3.0*team_env+4.0*(talent[None,:]-.5),7.0))
    team_plays=np.clip(np.rint(rng.normal(63.5+2.0*ge+1.5*team_env,6.0)),45,82).astype(int)
    pass_rate=np.clip(rng.normal(.575+.025*ge,.065),.38,.76)
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
            pts=rec+.1*(rec_y+rush_y)+6*tds[:,js]+3*(rec_y>=100)+3*(rush_y>=100)
            mat[:,idx[js]]=np.maximum(0,pts).astype(np.float32)

        if np.any(qmask):
            for j in np.where(qmask)[0]:
                qm=m[j]; pa=pass_att[:,ti]
                ypa=np.clip(rng.normal(6.6+1.5*qm,.85,size=n_sims),4.5,10.5)
                py=pa*ypa
                pass_td=np.maximum(0,np.rint(off_td[:,ti]*.72+rng.normal(0,.65,size=n_sims)).astype(int))
                ints=rng.poisson(max(.25,1.05-.45*qm),size=n_sims)
                ry=np.maximum(0,rus[:,j]*rng.normal(5.0,1.5,size=n_sims)); rtd=np.minimum(tds[:,j],2)
                pts=.04*py+4*pass_td-ints+.1*ry+6*rtd+3*(py>=300)
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

import itertools
import numpy as np
import pandas as pd

PORTFOLIO_ENGINE_VERSION = "Portfolio Intelligence V7"


def _z(v):
    v=np.asarray(v,dtype=float); sd=np.std(v)
    return (v-np.mean(v))/(sd if sd>1e-9 else 1.0)


def _normalize_player_preferences(player_preferences,size,default_max):
    prefs={}
    if not player_preferences: return prefs
    for raw_pid,raw in player_preferences.items():
        try: pid=int(raw_pid)
        except Exception: continue
        raw=raw or {}; boost=float(np.clip(raw.get("boost",0.0),-3,3)); mn=float(np.clip(raw.get("min",0),0,1)); mx=float(np.clip(raw.get("max",default_max),0,1)); mx=max(mx,mn)
        prefs[pid]={"boost":boost,"min":mn,"max":mx,"min_count":int(np.ceil(size*mn-1e-9)),"max_count":int(np.floor(size*mx+1e-9))}
    return prefs


def _lineup_team_game_sets(players,lineup_ids):
    if players is None or len(players)==0: return [set() for _ in lineup_ids],[set() for _ in lineup_ids]
    pteam=players.Team.astype(str).to_numpy(); pgame=players.Game.astype(str).to_numpy()
    teams=[]; games=[]
    for lu in lineup_ids:
        teams.append({pteam[i] for i in lu if 0<=i<len(pteam) and pteam[i] and pteam[i].lower()!="nan"})
        games.append({pgame[i] for i in lu if 0<=i<len(pgame) and pgame[i] and pgame[i].lower()!="nan"})
    return teams,games


def build_portfolio(contest_results,size=20,max_overlap=7,path_balance=1.25,leverage_weight=0.0,max_player_exposure=0.45,max_qb_exposure=0.30,player_preferences=None,players=None,max_team_exposure=1.0,max_game_exposure=1.0):
    """Portfolio Intelligence V7: select lineups as a portfolio of tournament bets.

    V7 preserves V6 exposure/overlap/core controls while adding scenario coverage,
    field-duplication awareness, elite-lineup protection, and contest-size-aware
    diversification. It rewards complementary ceiling paths instead of merely choosing
    the next highest individually ranked lineup.
    """
    if contest_results is None or contest_results.empty: return pd.DataFrame()
    x=contest_results.reset_index(drop=True).copy(); n=len(x); size=max(1,min(int(size),n)); max_overlap=int(np.clip(max_overlap,0,8))
    max_player_exposure=float(np.clip(max_player_exposure,.01,1)); max_qb_exposure=float(np.clip(max_qb_exposure,.01,1)); max_team_exposure=float(np.clip(max_team_exposure,.01,1)); max_game_exposure=float(np.clip(max_game_exposure,.01,1))
    gp=max(1,int(np.floor(size*max_player_exposure+1e-9))); qmax=max(1,int(np.floor(size*max_qb_exposure+1e-9))); tmax=max(1,int(np.floor(size*max_team_exposure+1e-9))); gmax=max(1,int(np.floor(size*max_game_exposure+1e-9)))
    prefs=_normalize_player_preferences(player_preferences,size,max_player_exposure)
    def num(c,d=0): return pd.to_numeric(x.get(c,d),errors="coerce").fillna(d).to_numpy(float)
    roi=num("Sim ROI %"); first=num("1st %"); top01=num("Top 0.1%"); top1=num("Top 1%"); ceil=num("Ceiling 95"); nuke=num("NUKE Score"); pathscore=num("Path Score",50); dup=num("Expected Duplicates",0); fieldpop=num("Field Popularity",0)
    base=.72*_z(roi)+.95*_z(first)+.78*_z(top01)+.42*_z(top1)+.58*_z(ceil)+.28*_z(nuke)+.15*_z(pathscore)
    # Protect truly elite tournament lineups from being diversified away.
    elite=.55*_z(first)+.35*_z(top01)+.25*_z(ceil)+.20*_z(roi)
    elite_rank=pd.Series(elite).rank(method="min",ascending=False).to_numpy(); elite_bonus=np.where(elite_rank<=max(3,int(np.ceil(n*.04))),.65,.0)
    # V3 field information: duplication/popularity is useful portfolio information, not a hard fade.
    leverage=.34*(-_z(dup))+.18*(-_z(fieldpop)); leverage=np.clip(leverage,-.75,.75)
    base=base+elite_bonus+leverage
    path=x.get("Strongest Path",pd.Series(["UNKNOWN"]*n)).fillna("UNKNOWN").astype(str).to_numpy(); qb=x.get("QB",pd.Series(["UNKNOWN"]*n)).fillna("UNKNOWN").astype(str).to_numpy(); stack=x.get("Stack",pd.Series(["UNKNOWN"]*n)).fillna("UNKNOWN").astype(str).to_numpy()
    ids=[tuple(map(int,lu)) for lu in x["_indices"]] if "_indices" in x.columns else [tuple() for _ in range(n)]; sets=[set(a) for a in ids]; pairs=[tuple(itertools.combinations(sorted(set(a)),2)) for a in ids]; triples=[tuple(itertools.combinations(sorted(set(a)),3)) for a in ids]
    overlap=np.zeros((n,n),dtype=np.int8)
    for i in range(n):
        for j in range(i+1,n): overlap[i,j]=overlap[j,i]=len(sets[i]&sets[j])
    team_sets,game_sets=_lineup_team_game_sets(players,ids); lineup_teams=[tuple(sorted(a)) for a in team_sets]; lineup_games=[tuple(sorted(a)) for a in game_sets]
    # Primary scenario = strongest path + QB + most concentrated game. This distinguishes
    # lineups that share players but are betting on materially different slate outcomes.
    scenario=[]
    for i in range(n):
        primary_game="NONE"
        if players is not None and len(players) and ids[i]:
            games=[str(players.iloc[p].Game) for p in ids[i] if 0<=p<len(players) and str(players.iloc[p].Game).lower()!="nan"]
            if games:
                vc=pd.Series(games).value_counts(); primary_game=str(vc.index[0])
        scenario.append(f"{path[i]} | {qb[i]} | {primary_game}")
    scenario=np.asarray(scenario,dtype=str)
    pref_adj=np.array([sum(.42*prefs.get(pid,{}).get("boost",0) for pid in lu) for lu in ids],dtype=float)
    vals,cnts=np.unique(path,return_counts=True); support=dict(zip(vals,cnts)); floor=max(2,int(np.ceil(size*.015))); viable={p for p,c in support.items() if c>=floor} or set(support); target=max(1.,size/max(1,len(viable)))
    maxpid=max((max(a) for a in ids if a),default=-1); pc=np.zeros(maxpid+1,dtype=np.int16); pmax=np.full(maxpid+1,gp,dtype=np.int16); pmin=np.zeros(maxpid+1,dtype=np.int16)
    for pid,p in prefs.items():
        if 0<=pid<=maxpid: pmax[pid]=p["max_count"]; pmin[pid]=p["min_count"]
    pathc={}; qbc={}; stackc={}; teamc={}; gamec={}; scenec={}; pairc={}; triplec={}; reasons={}; selected=[]; mask=np.zeros(n,dtype=bool)
    # Larger MME portfolios benefit more from scenario diversification; SE/3-max should
    # stay concentrated on the very best individual tournament lineups.
    diversity_scale=.55 if size<=3 else (.80 if size<=20 else 1.0)
    for pick in range(size):
        bi=-1; bs=-1e18; bm=None; sel=np.asarray(selected,dtype=int) if selected else None; denom=max(1,len(selected)); slots=size-pick-1
        for i in range(n):
            if mask[i]: continue
            lu=ids[i]
            if any(pid<=maxpid and pc[pid]>=pmax[pid] for pid in lu): continue
            if qbc.get(qb[i],0)>=qmax or any(teamc.get(t,0)>=tmax for t in lineup_teams[i]) or any(gamec.get(g,0)>=gmax for g in lineup_games[i]): continue
            if sel is not None:
                ovs=overlap[i,sel]; worst=int(ovs.max()); avg=float(ovs.mean())
                if worst>max_overlap: continue
            else: worst=0; avg=0
            cur=pathc.get(path[i],0); sat=cur/target; padj=float(path_balance)*diversity_scale*(.52*max(0,1-sat)-.38*max(0,sat-1)**2) if path[i] in viable else 0
            share=(cur+1)/max(1,len(selected)+1); dom=0
            if path[i] in viable and share>.45:
                ex=(share-.45)/.10; dom=float(path_balance)*diversity_scale*(.78*ex+.42*ex**2)
            qbshare=qbc.get(qb[i],0)/denom; stackshare=stackc.get(stack[i],0)/denom; conc=diversity_scale*(.22*max(0,qbshare-.20)+.08*max(0,stackshare-.55))
            redundancy=.09*max(0,avg-5.25)+.14*max(0,worst-6)
            maxpr=max((pairc.get(c,0) for c in pairs[i]),default=0); maxtr=max((triplec.get(c,0) for c in triples[i]),default=0); pload=sum(max(0,pairc.get(c,0)-4) for c in pairs[i]); tload=sum(max(0,triplec.get(c,0)-2) for c in triples[i]); corepen=.032*pload+.068*tload+.07*max(0,maxpr-10)**1.35+.14*max(0,maxtr-6)**1.45
            # Scenario saturation is V7's main portfolio-level intelligence. It is soft,
            # so a truly elite lineup can still enter a scenario already represented.
            sc=scenec.get(scenario[i],0); scenario_share=sc/denom; scenario_pen=diversity_scale*(.18*sc+.55*max(0,scenario_share-.12))
            # Game-bet concentration uses the most represented games in each lineup.
            game_pen=0.0
            if lineup_games[i]:
                game_pen=diversity_scale*.05*sum(max(0,gamec.get(g,0)/denom-.40) for g in lineup_games[i])
            minbonus=0
            for pid in lu:
                if 0<=pid<=maxpid:
                    need=max(0,int(pmin[pid])-int(pc[pid])); minbonus+=(1.10+2.4*(need/max(1,slots+1))) if need else 0
            score=float(base[i]+pref_adj[i]+minbonus+padj-dom-conc-redundancy-corepen-scenario_pen-game_pen)
            if score>bs: bi=i; bs=score; bm=(worst,maxpr,maxtr,sc)
        if bi<0:
            feasible=[i for i in range(n) if not mask[i] and not any(pid<=maxpid and pc[pid]>=pmax[pid] for pid in ids[i]) and qbc.get(qb[i],0)<qmax and not any(teamc.get(t,0)>=tmax for t in lineup_teams[i]) and not any(gamec.get(g,0)>=gmax for g in lineup_games[i])]
            if not feasible: break
            bi=max(feasible,key=lambda i:base[i]+pref_adj[i]); bm=(0,0,0,scenec.get(scenario[bi],0)); reasons[bi]="Elite remaining tournament upside; overlap relaxed to complete portfolio"
        else:
            worst,maxpr,maxtr,sc=bm
            if elite_bonus[bi]>0: label="Elite Ceiling"
            elif dup[bi] <= np.nanpercentile(dup,30) and first[bi] >= np.nanmedian(first): label="Low-Dup Leverage"
            elif sc==0: label="Scenario Diversifier"
            elif qbc.get(qb[bi],0)==0: label="Contrarian QB Path"
            else: label="GPP Upside"
            reasons[bi]=f"{label} | {path[bi]} | {scenario[bi].split(' | ')[-1]} | max overlap {worst} | expected dup {dup[bi]:.1f}"
        selected.append(bi); mask[bi]=True; pathc[path[bi]]=pathc.get(path[bi],0)+1; qbc[qb[bi]]=qbc.get(qb[bi],0)+1; stackc[stack[bi]]=stackc.get(stack[bi],0)+1; scenec[scenario[bi]]=scenec.get(scenario[bi],0)+1
        for pid in ids[bi]:
            if 0<=pid<=maxpid: pc[pid]+=1
        for t in lineup_teams[bi]: teamc[t]=teamc.get(t,0)+1
        for g in lineup_games[bi]: gamec[g]=gamec.get(g,0)+1
        for c in pairs[bi]: pairc[c]=pairc.get(c,0)+1
        for c in triples[bi]: triplec[c]=triplec.get(c,0)+1
    out=x.iloc[selected].copy().reset_index(drop=True)
    if not out.empty:
        out.insert(0,"Portfolio Slot",np.arange(1,len(out)+1)); out["Portfolio Reason"]=[reasons[i] for i in selected]; out["Portfolio Scenario"]=[scenario[i] for i in selected]
    out.attrs.update({"requested_size":size,"max_player_exposure":max_player_exposure,"max_qb_exposure":max_qb_exposure,"max_team_exposure":max_team_exposure,"max_game_exposure":max_game_exposure,"path_soft_cap":.45,"player_preferences":prefs,"max_pair_repeat":max(pairc.values(),default=0),"max_triple_repeat":max(triplec.values(),default=0),"scenario_count":len(scenec),"dominant_scenario_pct":100*max(scenec.values(),default=0)/max(1,len(selected))})
    unmet={}
    for pid,p in prefs.items():
        actual=int(pc[pid]) if 0<=pid<=maxpid else 0
        if actual<p["min_count"]: unmet[pid]={"requested":p["min_count"],"actual":actual}
    out.attrs["unmet_minimums"]=unmet
    return out


def portfolio_summary(portfolio):
    if portfolio is None or portfolio.empty: return pd.DataFrame(),{}
    path=portfolio.get("Strongest Path",pd.Series(["UNKNOWN"]*len(portfolio))).value_counts(); path_df=pd.DataFrame({"Path":path.index,"Lineups":path.values,"Portfolio %":np.round(100*path.values/len(portfolio),1)}).reset_index(drop=True); shares=path.to_numpy(float)/max(1,len(portfolio))
    stats={"lineups":len(portfolio),"requested_lineups":int(portfolio.attrs.get("requested_size",len(portfolio))),"avg_roi":float(pd.to_numeric(portfolio.get("Sim ROI %",0),errors="coerce").fillna(0).mean()),"paths":int(portfolio.get("Strongest Path",pd.Series(dtype=str)).nunique()),"qbs":int(portfolio.get("QB",pd.Series(dtype=str)).nunique()),"engine":PORTFOLIO_ENGINE_VERSION,"max_player_exposure":float(portfolio.attrs.get("max_player_exposure",1)),"max_qb_exposure":float(portfolio.attrs.get("max_qb_exposure",1)),"max_team_exposure":float(portfolio.attrs.get("max_team_exposure",1)),"max_game_exposure":float(portfolio.attrs.get("max_game_exposure",1)),"unmet_minimums":portfolio.attrs.get("unmet_minimums",{}),"dominant_path":str(path.index[0]) if len(path) else "UNKNOWN","dominant_path_pct":float(100*path.iloc[0]/len(portfolio)) if len(path) else 0,"path_hhi":float(np.sum(shares**2)) if len(shares) else 0,"path_soft_cap":float(portfolio.attrs.get("path_soft_cap",.45)),"max_pair_repeat":int(portfolio.attrs.get("max_pair_repeat",0)),"max_triple_repeat":int(portfolio.attrs.get("max_triple_repeat",0)),"scenarios":int(portfolio.attrs.get("scenario_count",0)),"dominant_scenario_pct":float(portfolio.attrs.get("dominant_scenario_pct",0))}
    return path_df,stats


def portfolio_player_exposure(players,portfolio):
    if players is None or portfolio is None or portfolio.empty or "_indices" not in portfolio.columns: return pd.DataFrame()
    counts={}
    for lu in portfolio["_indices"]:
        for pid in lu: counts[int(pid)]=counts.get(int(pid),0)+1
    prefs=portfolio.attrs.get("player_preferences",{}); rows=[]
    for pid,count in counts.items():
        p=players.iloc[pid]; pref=prefs.get(pid,{})
        rows.append({"Player":p.Name,"Pos":p.Position,"Team":p.Team,"Salary":int(p.Salary),"Lineups":count,"Exposure %":round(100*count/len(portfolio),1),"Boost":pref.get("boost",0),"Min %":round(100*pref.get("min",0),1),"Max %":round(100*pref.get("max",portfolio.attrs.get("max_player_exposure",1)),1)})
    return pd.DataFrame(rows).sort_values(["Exposure %","Salary"],ascending=[False,False]).reset_index(drop=True)


def portfolio_qb_exposure(portfolio):
    if portfolio is None or portfolio.empty or "QB" not in portfolio.columns: return pd.DataFrame()
    c=portfolio["QB"].fillna("UNKNOWN").astype(str).value_counts(); return pd.DataFrame({"QB":c.index,"Lineups":c.values,"Exposure %":np.round(100*c.values/len(portfolio),1)}).reset_index(drop=True)


def portfolio_team_game_exposure(players,portfolio):
    if players is None or portfolio is None or portfolio.empty or "_indices" not in portfolio.columns: return pd.DataFrame(),pd.DataFrame()
    ts,gs=_lineup_team_game_sets(players,[list(map(int,lu)) for lu in portfolio["_indices"]]); tc={}; gc={}
    for s in ts:
        for v in s: tc[v]=tc.get(v,0)+1
    for s in gs:
        for v in s: gc[v]=gc.get(v,0)+1
    tdf=pd.DataFrame([{"Team":k,"Lineups":v,"Exposure %":round(100*v/len(portfolio),1)} for k,v in tc.items()]).sort_values(["Exposure %","Team"],ascending=[False,True]).reset_index(drop=True) if tc else pd.DataFrame(columns=["Team","Lineups","Exposure %"])
    gdf=pd.DataFrame([{"Game":k,"Lineups":v,"Exposure %":round(100*v/len(portfolio),1)} for k,v in gc.items()]).sort_values(["Exposure %","Game"],ascending=[False,True]).reset_index(drop=True) if gc else pd.DataFrame(columns=["Game","Lineups","Exposure %"])
    return tdf,gdf


def portfolio_stack_exposure(portfolio):
    if portfolio is None or portfolio.empty: return pd.DataFrame()
    q=portfolio.get("QB",pd.Series(["UNKNOWN"]*len(portfolio))).fillna("UNKNOWN").astype(str); s=portfolio.get("Stack",pd.Series(["UNKNOWN"]*len(portfolio))).fillna("UNKNOWN").astype(str); d=pd.DataFrame({"QB":q,"Stack":s}); c=d.value_counts(["QB","Stack"]).reset_index(name="Lineups"); c["Exposure %"]=np.round(100*c["Lineups"]/len(portfolio),1); return c.sort_values(["Exposure %","QB"],ascending=[False,True]).reset_index(drop=True)


def portfolio_health(players,portfolio):
    if players is None or portfolio is None or portfolio.empty or "_indices" not in portfolio.columns: return {"flags":[],"top_core":pd.DataFrame(),"core_count":0}
    team_df,game_df=portfolio_team_game_exposure(players,portfolio); player_df=portfolio_player_exposure(players,portfolio); core={}
    for lu in [tuple(sorted(map(int,a))) for a in portfolio["_indices"]]:
        for c in itertools.combinations(lu,3): core[c]=core.get(c,0)+1
    rows=[]
    for c,count in sorted(core.items(),key=lambda kv:kv[1],reverse=True)[:25]: rows.append({"3-Player Core":" + ".join(str(players.iloc[p].Name) for p in c),"Lineups":count,"Exposure %":round(100*count/len(portfolio),1)})
    cdf=pd.DataFrame(rows); flags=[]
    if not player_df.empty and float(player_df.iloc[0]["Exposure %"])>=45: flags.append(f"Player concentration: {player_df.iloc[0]['Player']} appears in {player_df.iloc[0]['Exposure %']:.1f}% of lineups.")
    if not team_df.empty and float(team_df.iloc[0]["Exposure %"])>=65: flags.append(f"Team concentration: {team_df.iloc[0]['Team']} appears in {team_df.iloc[0]['Exposure %']:.1f}% of lineups.")
    if not game_df.empty and float(game_df.iloc[0]["Exposure %"])>=55: flags.append(f"Game concentration: {game_df.iloc[0]['Game']} appears in {game_df.iloc[0]['Exposure %']:.1f}% of lineups.")
    if not cdf.empty and float(cdf.iloc[0]["Exposure %"])>=25: flags.append(f"Core concentration: {cdf.iloc[0]['3-Player Core']} appears together in {cdf.iloc[0]['Exposure %']:.1f}% of lineups.")
    return {"flags":flags,"top_core":cdf,"core_count":len(core)}

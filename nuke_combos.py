from itertools import combinations
import pandas as pd


def combo_exposure_table(players, results):
    if results is None or results.empty or "_indices" not in results.columns:
        return pd.DataFrame(), pd.DataFrame()

    denom=len(results)
    pair_counts={}
    qb_anchor_counts={}
    qb_lineup_counts={}

    for lu in results["_indices"]:
        ids=list(lu)
        roster=players.iloc[ids]
        qbs=roster[roster.Position.eq("QB")]
        qb_idx=int(qbs.index[0]) if not qbs.empty else None
        if qb_idx is not None:
            qb_lineup_counts[qb_idx]=qb_lineup_counts.get(qb_idx,0)+1

        for a,b in combinations(ids,2):
            key=tuple(sorted((int(a),int(b))))
            pair_counts[key]=pair_counts.get(key,0)+1
            if qb_idx is not None and qb_idx in key:
                other=key[0] if key[1]==qb_idx else key[1]
                qb_anchor_counts[(qb_idx,other)]=qb_anchor_counts.get((qb_idx,other),0)+1

    pair_rows=[]
    for (a,b),count in pair_counts.items():
        ra=players.iloc[a]; rb=players.iloc[b]
        same_team=str(ra.Team)==str(rb.Team)
        same_game=str(ra.Game)==str(rb.Game)
        relation="Same Team" if same_team else "Same Game" if same_game else "Non-Stacked"
        pair_rows.append({
            "Player 1":ra.Name,"Pos 1":ra.Position,"Team 1":ra.Team,
            "Player 2":rb.Name,"Pos 2":rb.Position,"Team 2":rb.Team,
            "Combo Lineups":int(count),"Portfolio Combo %":round(100*count/denom,1),
            "Relationship":relation,
        })
    pairs=pd.DataFrame(pair_rows)
    if not pairs.empty:
        pairs=pairs.sort_values(["Portfolio Combo %","Combo Lineups"],ascending=False).reset_index(drop=True)

    qb_rows=[]
    for (q,o),count in qb_anchor_counts.items():
        rq=players.iloc[q]; ro=players.iloc[o]
        qden=max(1,qb_lineup_counts.get(q,0))
        same_team=str(rq.Team)==str(ro.Team)
        same_game=str(rq.Game)==str(ro.Game)
        relation="QB Stack" if same_team and ro.Position in {"WR","TE","RB"} else "Bring-back" if same_game and not same_team else "Non-Stacked"
        qb_rows.append({
            "QB":rq.Name,"QB Team":rq.Team,"Player":ro.Name,"Pos":ro.Position,"Team":ro.Team,
            "Combo Lineups":int(count),"Portfolio Combo %":round(100*count/denom,1),
            "% of QB Lineups":round(100*count/qden,1),"QB Lineups":int(qden),"Relationship":relation,
        })
    qb_pairs=pd.DataFrame(qb_rows)
    if not qb_pairs.empty:
        qb_pairs=qb_pairs.sort_values(["% of QB Lineups","Portfolio Combo %"],ascending=False).reset_index(drop=True)
    return pairs,qb_pairs

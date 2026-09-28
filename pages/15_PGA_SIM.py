import streamlit as st
import pandas as pd
import numpy as np
import io
from pathlib import Path
from nuke_nav import render_nav

st.set_page_config(page_title="NUKE PGA Sim", page_icon="⛳", layout="wide")
render_nav()

CAP=50000
ROSTER=6
DEFAULT=Path(__file__).resolve().parents[1]/"data"/"pga_current.csv"

def load_csv(src):
    d=pd.read_csv(src)
    req={"Name","ID","Salary","AvgPointsPerGame"}
    if not req.issubset(d.columns):
        raise ValueError("This does not look like a DraftKings PGA salary CSV.")
    d=d.copy()
    d["ID"]=pd.to_numeric(d["ID"],errors="coerce").astype("Int64")
    d["Salary"]=pd.to_numeric(d["Salary"],errors="coerce").fillna(0).astype(int)
    d["AvgPointsPerGame"]=pd.to_numeric(d["AvgPointsPerGame"],errors="coerce").fillna(0.0)
    d["Status"]=d.get("Status","").fillna("").astype(str).str.upper()
    d=d[~d["Status"].isin(["OUT","O","IR"])].dropna(subset=["ID"])
    d=d.drop_duplicates("ID").reset_index(drop=True)
    return d

def base_projection(d):
    f=d["AvgPointsPerGame"].to_numpy(float)
    sal=d["Salary"].to_numpy(float)
    fallback=np.interp(sal,[sal.min(),sal.max()],[42,78])
    return np.where(f>0,f,fallback)

def ownership_estimate(d):
    sal=d["Salary"].to_numpy(float)
    form=base_projection(d)
    z=.58*(sal-sal.mean())/(sal.std()+1e-9)+.42*(form-form.mean())/(form.std()+1e-9)
    raw=np.exp(np.clip(z,-2.5,2.5))
    # six roster spots across the field -> ownership sums to ~600%
    return raw/raw.sum()*600

def generate_candidates(d,n,min_salary,seed,locked_ids,excluded_ids):
    rng=np.random.default_rng(seed)
    ids=d["ID"].astype(int).to_numpy()
    salaries=d["Salary"].to_numpy(int)
    proj=base_projection(d)
    own=ownership_estimate(d)
    active=np.array([i not in excluded_ids for i in ids])
    locked_idx=np.where(np.isin(ids,list(locked_ids)) & active)[0]
    if len(locked_idx)>ROSTER:
        return []
    avail=np.where(active & ~np.isin(ids,list(locked_ids)))[0]
    # quality-weighted but stochastic candidate creation
    value=proj/np.maximum(salaries,1)*1000
    z=(value-value.mean())/(value.std()+1e-9)
    w=np.exp(np.clip(.45*z,-2,2)); w=w[avail]; w=w/w.sum()
    seen=set(); out=[]
    attempts=0; max_attempts=max(20000,n*80)
    while len(out)<n and attempts<max_attempts:
        attempts+=1
        need=ROSTER-len(locked_idx)
        if need<0 or len(avail)<need: break
        pick=rng.choice(avail,size=need,replace=False,p=w)
        idx=np.concatenate([locked_idx,pick])
        salary=int(salaries[idx].sum())
        if salary<min_salary or salary>CAP: continue
        key=tuple(sorted(ids[idx].tolist()))
        if key in seen: continue
        seen.add(key)
        out.append({"idx":idx,"salary":salary,"own_product":float(np.prod(np.clip(own[idx]/100,.002,.99)))})
    return out

def simulate_golfers(d,n_sims,seed):
    rng=np.random.default_rng(seed+991)
    mu=base_projection(d)
    salary=d["Salary"].to_numpy(float)
    # salary/form-informed cut probability; missed cuts score much lower
    strength=.55*(mu-mu.mean())/(mu.std()+1e-9)+.45*(salary-salary.mean())/(salary.std()+1e-9)
    make_cut=1/(1+np.exp(-(.25+strength)))
    cut=rng.random((n_sims,len(d)))<make_cut
    made=rng.normal(mu,14+np.maximum(0,7600-salary)/800,size=(n_sims,len(d)))
    missed=rng.normal(np.maximum(8,mu*.43),9,size=(n_sims,len(d)))
    # shared tournament environment + player volatility
    event=rng.normal(0,4,size=(n_sims,1))
    scores=np.where(cut,made,missed)+event
    return np.clip(scores,-10,None),make_cut

def evaluate(cands,sims,own):
    if not cands: return pd.DataFrame()
    rows=[]
    for j,c in enumerate(cands):
        s=sims[:,c["idx"]].sum(axis=1)
        rows.append({
            "_candidate":j,
            "Salary":c["salary"],
            "Mean":round(float(s.mean()),2),
            "Ceiling":round(float(np.quantile(s,.90)),2),
            "P95":round(float(np.quantile(s,.95)),2),
            "Top 1%":round(float(np.quantile(s,.99)),2),
            "Ownership Sum":round(float(own[c["idx"]].sum()),1),
            "Duplication Proxy":float(c["own_product"]),
        })
    r=pd.DataFrame(rows)
    for col in ["Mean","P95","Top 1%"]:
        r["_z_"+col]=(r[col]-r[col].mean())/(r[col].std()+1e-9)
    lev=-(np.log(np.maximum(r["Duplication Proxy"],1e-12)))
    lev=(lev-lev.mean())/(lev.std()+1e-9)
    r["NUKE Score"]=1.0*r["_z_Mean"]+1.25*r["_z_P95"]+.9*r["_z_Top 1%"]+.25*lev
    return r.sort_values("NUKE Score",ascending=False).reset_index(drop=True)

def lineup_names(c,d):
    return [str(d.iloc[i]["Name"]) for i in c["idx"]]

def export_csv(portfolio,cands,d):
    rows=[]
    for rank,row in portfolio.reset_index(drop=True).iterrows():
        c=cands[int(row["_candidate"])]
        ps=d.iloc[c["idx"]].sort_values("Salary",ascending=False)
        vals=[f'{r["Name"]} ({int(r["ID"])})' for _,r in ps.iterrows()]
        rows.append({**{f"G{i+1}":vals[i] for i in range(6)},
                     "Salary":int(row["Salary"]),"NUKE Score":round(float(row["NUKE Score"]),3),
                     "Mean":row["Mean"],"P95":row["P95"],"Top 1%":row["Top 1%"]})
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")

st.title("⛳ NUKE PGA")
st.caption("DraftKings PGA tournament simulation · 6 golfers · $50,000 salary cap")

up=st.file_uploader("Optional: upload a different DraftKings PGA salary CSV",type=["csv"])
try:
    if up is not None:
        golfers=load_csv(up); source="Uploaded slate"
    elif DEFAULT.exists():
        golfers=load_csv(DEFAULT); source="Loaded automatically"
    else:
        st.info("Upload this week's DraftKings PGA salary CSV to begin.")
        st.stop()
except Exception as e:
    st.error(str(e)); st.stop()

event=str(golfers["Game Info"].iloc[0]) if "Game Info" in golfers.columns and len(golfers) else "PGA"
st.success(f"{source}: {event} · {len(golfers)} active golfers")

m1,m2,m3,m4=st.columns(4)
m1.metric("Golfers",len(golfers)); m2.metric("Roster","6 G"); m3.metric("Salary Cap","$50,000"); m4.metric("Event",event)

st.subheader("🏌️ Golfer Pool")
st.caption("Include/exclude golfers, lock golfers into every candidate lineup, and optionally boost or limit portfolio exposure.")
editor=golfers[["ID","Name","Salary","AvgPointsPerGame"]].copy()
editor.insert(0,"In",True); editor.insert(1,"Lock",False); editor["Boost %"]=0; editor["Min %"]=0; editor["Max %"]=100
edited=st.data_editor(editor,hide_index=True,use_container_width=True,height=430,
    disabled=["ID","Name","Salary","AvgPointsPerGame"],
    column_config={
      "In":st.column_config.CheckboxColumn("In"),
      "Lock":st.column_config.CheckboxColumn("🔒 Lock"),
      "Salary":st.column_config.NumberColumn("Salary",format="$%d"),
      "AvgPointsPerGame":st.column_config.NumberColumn("DK FPPG",format="%.1f"),
      "Boost %":st.column_config.NumberColumn("Boost %",min_value=-50,max_value=100,step=5),
      "Min %":st.column_config.NumberColumn("Min %",min_value=0,max_value=100,step=5),
      "Max %":st.column_config.NumberColumn("Max %",min_value=0,max_value=100,step=5),
    },key="pga_pool_editor")

with st.sidebar:
    st.markdown("## ⛳ PGA SIM")
    candidates_n=st.number_input("Candidate lineups",500,20000,5000,500, key="pga_candidates")
    universes=st.number_input("Tournament universes",250,10000,3000,250,key="pga_universes")
    portfolio_n=st.number_input("Portfolio lineups",1,150,20,1,key="pga_portfolio")
    min_salary=st.number_input("Minimum salary",30000,50000,49000,100,key="pga_min_salary")
    max_player=st.slider("Max golfer exposure",1,100,60,key="pga_max_exp")
    field_size=st.number_input("Contest field size",2,1000000,4444,1,key="pga_field")
    entry_fee=st.number_input("Entry fee ($)",0.0,10000.0,100.0,1.0,key="pga_fee")
    first_prize=st.number_input("1st prize ($)",0.0,10000000.0,100000.0,1000.0,key="pga_first")

if st.button("☢️ RUN PGA CONTEST SIM",type="primary",use_container_width=True):
    included=set(edited.loc[edited["In"],"ID"].astype(int))
    excluded=set(edited.loc[~edited["In"],"ID"].astype(int))
    locked=set(edited.loc[edited["Lock"] & edited["In"],"ID"].astype(int))
    if len(locked)>6:
        st.error("You can lock at most 6 golfers."); st.stop()
    seed=int(np.random.default_rng().integers(1,2_000_000_000))
    with st.spinner("Generating PGA lineups and simulating tournament outcomes..."):
        cands=generate_candidates(golfers,int(candidates_n),int(min_salary),seed,locked,excluded)
        if not cands:
            st.error("No legal 6-golfer lineups were generated. Lower the salary floor or loosen the pool."); st.stop()
        sims,cut_prob=simulate_golfers(golfers,int(universes),seed)
        own=ownership_estimate(golfers)
        results=evaluate(cands,sims,own)
        # apply user boosts to selection score
        boosts=dict(zip(edited["ID"].astype(int),edited["Boost %"].astype(float)))
        for ri in results.index:
            c=cands[int(results.at[ri,"_candidate"])]
            results.at[ri,"NUKE Score"] += sum(boosts.get(int(golfers.iloc[i]["ID"]),0) for i in c["idx"])/100
        results=results.sort_values("NUKE Score",ascending=False).reset_index(drop=True)
        # greedy diversified portfolio honoring max exposure + per-golfer max/min as best effort
        counts={int(x):0 for x in golfers["ID"]}
        selected=[]
        target=int(portfolio_n)
        personal_max=dict(zip(edited["ID"].astype(int),edited["Max %"].astype(float)))
        for _,r in results.iterrows():
            c=cands[int(r["_candidate"])]
            ids=[int(golfers.iloc[i]["ID"]) for i in c["idx"]]
            ok=True
            for pid in ids:
                cap=min(float(max_player),personal_max.get(pid,100.0))
                if counts.get(pid,0)+1 > max(1,int(np.floor(target*cap/100+1e-9))):
                    ok=False; break
            if ok:
                selected.append(r)
                for pid in ids: counts[pid]=counts.get(pid,0)+1
            if len(selected)>=target: break
        portfolio=pd.DataFrame(selected)
        st.session_state["pga_results"]=(results,cands,portfolio,golfers,own,cut_prob,seed)

if "pga_results" in st.session_state:
    results,cands,portfolio,golfers,own,cut_prob,seed=st.session_state["pga_results"]
    st.divider(); st.header("🏆 PGA Contest Sim Results")
    a,b,c,d=st.columns(4)
    a.metric("Candidates",len(results)); b.metric("Portfolio",len(portfolio)); c.metric("Universes",f"{universes:,}"); d.metric("Seed",seed)
    st.subheader("NUKE PGA Portfolio")
    show=[]
    for rank,r in portfolio.reset_index(drop=True).iterrows():
        cand=cands[int(r["_candidate"])]
        show.append({"#":rank+1,"Golfers":" · ".join(lineup_names(cand,golfers)),"Salary":int(r["Salary"]),
                     "Mean":r["Mean"],"P95":r["P95"],"Top 1%":r["Top 1%"],
                     "Own Sum %":r["Ownership Sum"],"NUKE Score":round(float(r["NUKE Score"]),3)})
    st.dataframe(pd.DataFrame(show),hide_index=True,use_container_width=True,height=430)
    st.download_button("DOWNLOAD PGA PORTFOLIO + STATS CSV",export_csv(portfolio,cands,golfers),
                       file_name="nuke_pga_portfolio.csv",mime="text/csv",type="primary",use_container_width=True)

    st.subheader("Golfer Exposure")
    exp=[]
    denom=max(1,len(portfolio))
    for i,row in golfers.iterrows():
        pid=int(row["ID"]); ct=0
        for _,r in portfolio.iterrows():
            if i in cands[int(r["_candidate"])]["idx"]: ct+=1
        if ct:
            exp.append({"Golfer":row["Name"],"Salary":int(row["Salary"]),"Lineups":ct,
                        "Exposure %":round(100*ct/denom,1),"Est. Own %":round(float(own[i]),1),
                        "Make Cut %":round(float(cut_prob[i])*100,1)})
    st.dataframe(pd.DataFrame(exp).sort_values(["Exposure %","Salary"],ascending=[False,False]),hide_index=True,use_container_width=True)

    with st.expander("Top simulated candidate lineups"):
        top=[]
        for rank,r in results.head(100).iterrows():
            cand=cands[int(r["_candidate"])]
            top.append({"Rank":rank+1,"Golfers":" · ".join(lineup_names(cand,golfers)),"Salary":int(r["Salary"]),
                        "Mean":r["Mean"],"P95":r["P95"],"Top 1%":r["Top 1%"],"NUKE Score":round(float(r["NUKE Score"]),3)})
        st.dataframe(pd.DataFrame(top),hide_index=True,use_container_width=True)

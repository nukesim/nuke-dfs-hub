import streamlit as st
import pandas as pd
import numpy as np
import itertools
import math
import re
import unicodedata
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from nuke_nav import render_nav

st.set_page_config(page_title="NUKE UFC Single Entry", page_icon="🥊", layout="wide")
render_nav()

CAP = 50000
ROSTER = 6

# Both UFC tools use the same versioned DraftKings salary file by default.
# An uploaded DK CSV overrides the default for the user's current session.
DEFAULT_DK = Path(__file__).resolve().parents[1] / "data" / "mma_current.csv"

# Avoid carrying fighter-specific volatility assumptions from older fight cards.
FIGHT_VOL = {}

st.markdown("""
<style>
:root{
  --green:#19c37d; --yellow:#f2c94c; --red:#ff5d5d;
  --muted:#8d99a8; --panel:rgba(255,255,255,.028); --border:rgba(255,255,255,.10);
}
.block-container{max-width:1680px;padding-top:.8rem!important}
h1,h2,h3{letter-spacing:-.025em}
.se-hero{
  border:1px solid rgba(25,195,125,.35); border-radius:20px; padding:18px 20px;
  background:radial-gradient(circle at 0 0,rgba(25,195,125,.10),transparent 34%),rgba(255,255,255,.02);
  margin-bottom:12px;
}
.se-kicker{font-size:.68rem;font-weight:1000;letter-spacing:.14em;color:var(--green);text-transform:uppercase}
.se-title{font-size:2rem;font-weight:1000;line-height:1.03;margin-top:4px}
.se-sub{color:var(--muted);font-size:.88rem;margin-top:6px}
.f-card{
  border:1px solid var(--border);border-radius:16px;padding:11px 12px;margin-bottom:9px;
  background:linear-gradient(180deg,rgba(255,255,255,.035),rgba(255,255,255,.012));
}
.f-rank{font-size:.68rem;font-weight:1000;letter-spacing:.10em;color:var(--muted)}
.f-name{font-size:1.03rem;font-weight:1000;margin-top:2px}
.f-meta{font-size:.72rem;color:var(--muted);margin-top:4px}
.f-score{font-size:1.45rem;font-weight:1000}
.tier-core{border-color:rgba(25,195,125,.52)!important;background:rgba(25,195,125,.045)!important}
.tier-strong{border-color:rgba(80,170,255,.42)!important}
.tier-leverage{border-color:rgba(242,201,76,.45)!important}
.tier-thin{border-color:rgba(255,150,80,.38)!important}
.tier-fade{opacity:.62}
.pill{display:inline-block;border-radius:999px;padding:3px 7px;font-size:.66rem;font-weight:950;margin-right:4px;border:1px solid rgba(255,255,255,.11)}
.pill-core{color:#7fe0b5;border-color:rgba(25,195,125,.4);background:rgba(25,195,125,.08)}
.pill-lev{color:#f2c94c;border-color:rgba(242,201,76,.4);background:rgba(242,201,76,.06)}
.lineup-card{
 border:1px solid rgba(25,195,125,.42);border-radius:18px;padding:15px 16px;
 background:linear-gradient(180deg,rgba(25,195,125,.06),rgba(255,255,255,.012));margin:6px 0 12px 0
}
.lu-rank{font-size:.7rem;font-weight:1000;letter-spacing:.12em;color:#19c37d}
.lu-fighters{font-size:1.1rem;font-weight:900;line-height:1.5;margin-top:4px}
.small-muted{font-size:.75rem;color:var(--muted)}
[data-testid="stMetric"]{border:1px solid var(--border);border-radius:14px;padding:9px 11px;background:var(--panel)}
</style>
""", unsafe_allow_html=True)

def american_prob(o):
    o = float(o)
    return (-o) / ((-o) + 100.0) if o < 0 else 100.0 / (o + 100.0)

def norm_name(x):
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", x)

def slug_name(x):
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", x).strip("-")

def load_dk_csv(upload):
    d = pd.read_csv(upload).copy()
    req = {"Name", "ID", "Salary", "Game Info"}
    if not req.issubset(d.columns):
        raise ValueError("Upload the DraftKings MMA Classic salary CSV (Name, ID, Salary, Game Info).")
    d["ID"] = pd.to_numeric(d["ID"], errors="coerce").astype("Int64")
    d["Salary"] = pd.to_numeric(d["Salary"], errors="coerce").fillna(0).astype(int)
    d = d.dropna(subset=["ID"]).drop_duplicates("ID").reset_index(drop=True)
    d["DK_ID"] = d["ID"].astype(int).astype(str)
    raw = d["Game Info"].astype(str).str.replace(r"\s+\d{1,2}/\d{1,2}/\d{4}.*$", "", regex=True)
    d["Fight"] = raw
    d["Opp"] = ""
    for _, idxs in d.groupby("Fight").groups.items():
        z = list(idxs)
        if len(z) == 2:
            d.loc[z[0], "Opp"] = d.loc[z[1], "Name"]
            d.loc[z[1], "Opp"] = d.loc[z[0], "Name"]
    # Accept market odds only for the same fighter/opponent/full DK bout.
    # Never silently apply a previous card's moneyline to today's fighter.
    d["Moneyline"] = np.nan
    snapshot = DEFAULT_DK.parent / "mma_market.csv"
    if snapshot.exists():
        market = pd.read_csv(snapshot)
        needed = {"Name", "Opp", "Game Info", "Moneyline"}
        if needed.issubset(market.columns):
            by_match = {
                (norm_name(r["Name"]), norm_name(r["Opp"]), str(r["Game Info"])):
                    pd.to_numeric(r["Moneyline"], errors="coerce")
                for _, r in market.iterrows()
            }
            d["Moneyline"] = [
                by_match.get((norm_name(r["Name"]), norm_name(r["Opp"]), str(r["Game Info"])), np.nan)
                for _, r in d.iterrows()
            ]
    start = pd.to_datetime(
        d["Game Info"].astype(str).str.extract(r"(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}[AP]M)")[0],
        format="%m/%d/%Y %I:%M%p", errors="coerce"
    )
    d["Rounds"] = np.where(start.eq(start.max()), 5, 3)
    return d[["ID", "Name", "Opp", "Salary", "Moneyline", "Rounds", "Fight", "DK_ID", "Game Info"]]

@st.cache_data(ttl=21600, show_spinner=False)
def fetch_stats(name, refresh_nonce=0):
    """Lightweight live style-rate fetch. Returns neutral values if upstream blocks."""
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.ufcalendar.com/fighters/{slug_name(name)}/stats"
    try:
        r = requests.get(url, timeout=8, headers=headers)
        if not r.ok:
            return {}
        txt = re.sub(r"<[^>]+>", " ", r.text)
        txt = re.sub(r"\s+", " ", txt)
        section = re.search(r"UFC career\s+(.*?)\s+(?:Tracked fights|Percentiles compare|Events Tonight)", txt, re.I | re.S)
        if not section:
            return {}
        s = section.group(1)
        def grab(labels):
            for label in labels:
                m = re.search(label + r"\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*%?", s, re.I)
                if m:
                    return float(m.group(1))
            return np.nan
        return {
            "SLpM": grab([r"Significant strikes"]),
            "SApM": grab([r"SApM"]),
            "TD Avg": grab([r"Takedowns"]),
            "TD Def %": grab([r"TD Def\.?" ]),
            "Sub Avg": grab([r"Submission attempts"]),
        }
    except Exception:
        return {}

def enrich_stats(d, nonce):
    out = d.copy()
    stats = {}
    names = out["Name"].astype(str).tolist()
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(names)))) as ex:
        futs = {ex.submit(fetch_stats, n, nonce): n for n in names}
        for f in as_completed(futs):
            n = futs[f]
            try:
                stats[norm_name(n)] = f.result() or {}
            except Exception:
                stats[norm_name(n)] = {}
    for c in ["SLpM", "SApM", "TD Avg", "TD Def %", "Sub Avg"]:
        out[c] = np.nan
    for i, r in out.iterrows():
        for c, v in stats.get(norm_name(r["Name"]), {}).items():
            out.at[i, c] = v
    return out

def fair_win_probs(d):
    p = np.full(len(d), .5, dtype=float)
    for _, idxs in d.groupby("Fight").groups.items():
        z = list(idxs)
        if len(z) != 2:
            continue
        a, b = z
        oa, ob = d.loc[a, "Moneyline"], d.loc[b, "Moneyline"]
        if pd.notna(oa) and pd.notna(ob):
            pa, pb = american_prob(oa), american_prob(ob)
            p[a], p[b] = pa / (pa + pb), pb / (pa + pb)
        else:
            diff = float(d.loc[a, "Salary"]) - float(d.loc[b, "Salary"])
            pa = 1.0 / (1.0 + math.exp(-diff / 1800.0))
            p[a], p[b] = pa, 1 - pa
    return p

def zfill(series):
    a = pd.to_numeric(series, errors="coerce").to_numpy(float)
    if not np.isfinite(a).any():
        return np.zeros(len(a))
    med = np.nanmedian(a)
    a = np.where(np.isfinite(a), a, med)
    sd = np.std(a)
    return (a - np.mean(a)) / (sd + 1e-9)

def build_model(d):
    x = d.copy().reset_index(drop=True)
    win = fair_win_probs(x)
    z_slpm = zfill(x["SLpM"])
    z_sapm = zfill(x["SApM"])
    z_td = zfill(x["TD Avg"])
    z_sub = zfill(x["Sub Avg"])
    z_tddef = zfill(x["TD Def %"])
    activity = .42*z_slpm + .38*z_td + .20*z_sub
    defense = .55*z_tddef - .45*z_sapm
    five = (x["Rounds"].to_numpy(int) == 5).astype(float)

    finish = np.zeros(len(x), float)
    for i, r in x.iterrows():
        base_fight = FIGHT_VOL.get(frozenset((r["Name"], r["Opp"])), 0.52)
        # Allocate the fight finish probability toward the better side, while preserving upset finishes.
        share = .42 + .36*win[i]
        finish[i] = np.clip(base_fight * share + .035*activity[i] - .015*defense[i], .12, .68)

    decision_win_pts = 68 + 13*activity + 12*five
    finish_pts = 110 + 12*activity + 5*five
    lose_pts = 30 + 7*z_slpm + 5*five
    mean = win * (finish*finish_pts + (1-finish)*decision_win_pts) + (1-win)*lose_pts
    ceiling = mean + 40*finish + 13*np.maximum(activity, 0) + 8*five

    # Ownership model: 600 total roster percentage across a six-fighter field.
    salz = (x["Salary"].to_numpy(float) - x["Salary"].mean()) / (x["Salary"].std() + 1e-9)
    mz = (mean - mean.mean()) / (mean.std() + 1e-9)
    raw = np.exp(np.clip(.55*salz + .65*mz + .45*(win-.5)*2 + .20*finish, -2.6, 2.6))
    own = raw / raw.sum() * 600.0

    ownz = (own-own.mean())/(own.std()+1e-9)
    value = mean / np.maximum(x["Salary"].to_numpy(float)/1000.0, .1)
    valz = (value-value.mean())/(value.std()+1e-9)
    ceilz = (ceiling-ceiling.mean())/(ceiling.std()+1e-9)
    winz = (win-win.mean())/(win.std()+1e-9)
    finz = (finish-finish.mean())/(finish.std()+1e-9)
    lev = .55*ceilz + .45*winz + .35*finz + .30*valz - .35*ownz
    rating = 50 + 12*lev
    x["Win %"] = win*100
    x["Finish %"] = finish*100
    x["Projection"] = mean
    x["Ceiling"] = ceiling
    x["pOwn%"] = own
    x["Value"] = value
    x["SE Rating"] = np.clip(rating, 1, 99)
    return x

def tier_for(rank, rating, own, win):
    if rank <= 5 and rating >= 57:
        return "CORE"
    if rank <= 11:
        return "STRONG"
    if rating >= 52 and own < 25:
        return "LEVERAGE"
    if win < 30 and rating < 47:
        return "FADE"
    return "THIN"

def simulate_card(d, n_sims, seed):
    rng = np.random.default_rng(seed)
    n = len(d)
    scores = np.zeros((n_sims, n), dtype=np.float32)
    winp = d["Win %"].to_numpy(float)/100.0
    finishp = d["Finish %"].to_numpy(float)/100.0
    activity = .42*zfill(d["SLpM"]) + .38*zfill(d["TD Avg"]) + .20*zfill(d["Sub Avg"])
    for _, idxs in d.groupby("Fight").groups.items():
        z = list(idxs)
        if len(z) != 2:
            continue
        a, b = z
        aw = rng.random(n_sims) < winp[a]
        for w, l, mask in [(a, b, aw), (b, a, ~aw)]:
            rows = np.where(mask)[0]
            if not len(rows):
                continue
            is5 = int(d.loc[w, "Rounds"]) == 5
            fin = rng.random(len(rows)) < finishp[w]
            if is5:
                round_probs = np.array([.34,.25,.18,.13,.10])
            else:
                round_probs = np.array([.47,.31,.22])
            rd = np.zeros(len(rows), dtype=int)
            if fin.any():
                rd[fin] = rng.choice(np.arange(1, len(round_probs)+1), size=int(fin.sum()), p=round_probs)
            # Winner scoring approximates DK's finish bonuses plus pace/grappling opportunity.
            bonus_map = np.array([127, 107, 89, 83, 81], float)
            wbase = np.where(fin, bonus_map[np.maximum(rd-1,0)], 102 if is5 else 76)
            wbase += 8*activity[w]
            lbase = np.where(fin, 11 + 11*rd, 63 if is5 else 43)
            lbase += 4*activity[l]
            scores[rows, w] = np.clip(wbase + rng.normal(0, 11, len(rows)), 0, 175)
            scores[rows, l] = np.clip(lbase + rng.normal(0, 9, len(rows)), 0, 115)
    return scores

def enumerate_candidates(d, include, locked, min_salary, max_salary, max_dogs, keep, seed):
    rng = np.random.default_rng(seed)
    ids = d["ID"].astype(int).to_numpy()
    sal = d["Salary"].astype(int).to_numpy()
    fight = d["Fight"].astype(str).to_numpy()
    win = d["Win %"].to_numpy(float)/100
    proj = d["Projection"].to_numpy(float)
    ceil = d["Ceiling"].to_numpy(float)
    own = d["pOwn%"].to_numpy(float)
    rating = d["SE Rating"].to_numpy(float)

    pool_idx = [i for i, pid in enumerate(ids) if int(pid) in include]
    lock_idx = [i for i, pid in enumerate(ids) if int(pid) in locked]
    rest = [i for i in pool_idx if i not in lock_idx]
    need = ROSTER-len(lock_idx)
    if need < 0:
        return []
    out = []
    for comb in itertools.combinations(rest, need):
        idx = tuple(sorted(lock_idx + list(comb)))
        if len(set(fight[list(idx)])) < ROSTER:
            continue
        salary = int(sal[list(idx)].sum())
        if salary < min_salary or salary > max_salary:
            continue
        dogs = int(np.sum(win[list(idx)] < .5))
        if dogs > max_dogs:
            continue
        own_sum = float(own[list(idx)].sum())
        low = int(np.sum(own[list(idx)] < 18))
        chalk = int(np.sum(own[list(idx)] > 35))
        leverage = float(np.sum(np.maximum(rating[list(idx)]-50,0) * np.maximum(25-own[list(idx)],0)/25))
        # Single-entry pre-score: ceiling first, then leverage; don't reward reckless all-dog/all-punt builds.
        pre = (
            .55*proj[list(idx)].sum() + .62*ceil[list(idx)].sum()
            + 1.8*leverage + 2.4*min(low,2) - 2.1*max(0,low-3)
            - .55*max(0, chalk-3) + .0012*(salary-47000)
            + rng.normal(0, 2.5)
        )
        pop = float(np.prod(np.clip(own[list(idx)]/100.0, .005, .95)))
        out.append({"idx": idx, "salary": salary, "own_sum": own_sum, "dogs": dogs,
                    "low": low, "pre": pre, "pop": pop})
    out.sort(key=lambda r: r["pre"], reverse=True)
    # Keep a quality core plus some lower-owned tail outcomes.
    if len(out) > keep:
        core_n = int(keep*.82)
        core = out[:core_n]
        tail = out[core_n:]
        if tail:
            weights = np.array([1/(1+r["pop"]*1000) for r in tail], float)
            weights /= weights.sum()
            take = min(keep-core_n, len(tail))
            pick = rng.choice(len(tail), size=take, replace=False, p=weights)
            out = core + [tail[int(i)] for i in pick]
        else:
            out = core
    return out

def evaluate_candidates(cands, sims, d, field_size, seed):
    rng = np.random.default_rng(seed+991)
    n_sims = sims.shape[0]
    # Sample a realistic field from the candidate pool using ownership product and near-cap salary preference.
    pops = np.array([max(c["pop"], 1e-12) for c in cands], float)
    left = np.array([CAP-c["salary"] for c in cands], float)
    fw = np.power(pops, .42) * np.exp(-np.maximum(left-700,0)/2600)
    fw /= fw.sum()
    field_idx = rng.choice(len(cands), size=field_size, replace=True, p=fw)
    field_scores = np.empty((field_size, n_sims), dtype=np.float32)
    for j, ci in enumerate(field_idx):
        field_scores[j] = sims[:, list(cands[int(ci)]["idx"])].sum(axis=1)
    win_thr = field_scores.max(axis=0)
    top1_thr = np.quantile(field_scores, .99, axis=0)
    cash_thr = np.quantile(field_scores, .80, axis=0)

    # Expected entries on the exact lineup is derived from the field sampling distribution.
    expected_dups = field_size * fw
    rows = []
    for j, c in enumerate(cands):
        sc = sims[:, list(c["idx"])].sum(axis=1)
        rows.append({
            "_candidate": j,
            "Salary": c["salary"],
            "Left": CAP-c["salary"],
            "Mean": float(np.mean(sc)),
            "P90": float(np.quantile(sc,.90)),
            "P95": float(np.quantile(sc,.95)),
            "P99": float(np.quantile(sc,.99)),
            "Win %": float(np.mean(sc >= win_thr)*100),
            "Top 1% %": float(np.mean(sc >= top1_thr)*100),
            "Cash %": float(np.mean(sc >= cash_thr)*100),
            "Own Sum %": c["own_sum"],
            "Underdogs": c["dogs"],
            "Low-Owned": c["low"],
            "Expected Dup": float(expected_dups[j]),
        })
    r = pd.DataFrame(rows)
    score = np.zeros(len(r))
    for col, w in [("Win %", 2.2), ("Top 1% %", 1.25), ("P99", .85), ("P95", .35)]:
        z = (r[col]-r[col].mean())/(r[col].std()+1e-9)
        score += w*z
    dupz = (r["Expected Dup"]-r["Expected Dup"].mean())/(r["Expected Dup"].std()+1e-9)
    ownz = (r["Own Sum %"]-r["Own Sum %"].mean())/(r["Own Sum %"].std()+1e-9)
    score -= .48*dupz + .12*np.maximum(ownz,0)
    # Leaving a little salary is a tiebreaker, not a goal.
    score += .08*np.clip(r["Left"].to_numpy(), 0, 1200)/1200
    r["SE Score"] = score
    return r.sort_values(["SE Score", "Win %", "P99"], ascending=False).reset_index(drop=True)

def lineup_names(c, d):
    return [str(d.iloc[i]["Name"]) for i in c["idx"]]

def dk_export_lineups(results, cands, d, n=10):
    if "DK_ID" not in d or not d["DK_ID"].astype(str).str.len().gt(0).all():
        return None
    rows = []
    for _, r in results.head(n).iterrows():
        c = cands[int(r["_candidate"])]
        ps = d.iloc[list(c["idx"])].sort_values("Salary", ascending=False)
        vals = [f'{x["Name"]} ({x["DK_ID"]})' for _, x in ps.iterrows()]
        rows.append({f"F{i+1}": vals[i] for i in range(6)})
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")

st.markdown("""
<div class="se-hero">
  <div class="se-kicker">Single-entry tournament engine</div>
  <div class="se-title">🥊 NUKE UFC — 1,189-Entry Hunter</div>
  <div class="se-sub">Built for one lineup. The model rewards first-place paths, fight-winning ceiling, finish equity and useful leverage — while penalizing duplicate-prone chalk construction.</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 🎯 SINGLE ENTRY")
    field_size = st.number_input("Contest entries", 100, 10000, 1189, 1)
    n_sims = st.number_input("Card simulations", 1000, 10000, 5000, 500)
    candidate_keep = st.number_input("Lineups to fully evaluate", 1000, 8000, 3500, 250)
    min_salary = st.number_input("Minimum salary", 42000, 50000, 47500, 100)
    max_salary = st.number_input("Maximum salary", 45000, 50000, 50000, 100)
    max_dogs = st.slider("Max underdogs", 0, 4, 2)
    st.caption("For this field size, NUKE defaults to quality leverage — not six contrarian darts.")

with st.expander("📥 Optional — upload the actual DraftKings MMA salary CSV", expanded=False):
    upload = st.file_uploader("DraftKings MMA Classic salaries", type=["csv"], key="ufc_se_upload")
    st.caption("Defaults to the same current DraftKings slate as MMA 150-Max; upload a different Classic salary CSV to override it. Real DK fighter IDs are preserved for lineup exports.")

try:
    fighters = load_dk_csv(upload if upload is not None else DEFAULT_DK)
except Exception as e:
    st.error(str(e))
    st.stop()

# Prevent cached lineup results and editable overrides from leaking between slates.
slate_signature = tuple(sorted(
    (int(r["ID"]), int(r["Salary"]), str(r["Fight"]))
    for _, r in fighters.iterrows()
))
if st.session_state.get("ufc_se_slate_signature") != slate_signature:
    for key in ("ufc_se_results", "ufc_se_prefs", "ufc_se_editor"):
        st.session_state.pop(key, None)
    st.session_state["ufc_se_slate_signature"] = slate_signature

slate_date = pd.to_datetime(
    fighters["Game Info"].astype(str).str.extract(r"(\d{1,2}/\d{1,2}/\d{4})")[0],
    format="%m/%d/%Y", errors="coerce"
).dropna()
if not slate_date.empty:
    st.caption(f"DraftKings slate: {slate_date.iloc[0]:%B %d, %Y} · {'Uploaded CSV' if upload is not None else 'Shared MMA 150-Max CSV'} · Real DK fighter IDs")
if fighters["Moneyline"].notna().sum() == 0:
    st.caption("No verified odds snapshot for this card: win probabilities use a salary-based prior until odds are supplied in the fighter editor.")

nonce = int(st.session_state.get("ufc_se_nonce", 0))
with st.spinner("Pulling live fighter style rates..."):
    fighters = enrich_stats(fighters, nonce)
fighters = build_model(fighters)

# User-editable market inputs.
editor = fighters[["ID","Name","Opp","Salary","Moneyline","pOwn%","Finish %","Win %","Projection","Ceiling","SE Rating","Fight"]].copy()
editor.insert(0, "In", True)
editor.insert(1, "Lock", False)
prefs = st.session_state.get("ufc_se_prefs", {})
for i, r in editor.iterrows():
    p = prefs.get(str(int(r["ID"])), {})
    for c in ["In","Lock","pOwn%","Finish %","Moneyline"]:
        if c in p:
            editor.at[i,c] = p[c]

m1,m2,m3,m4 = st.columns(4)
m1.metric("Fights", int(fighters["Fight"].nunique()))
m2.metric("Fighters", len(fighters))
m3.metric("Field", f"{int(field_size):,}")
m4.metric("Goal", "1st place")

if st.button("🔄 Refresh fighter data", use_container_width=False):
    st.session_state["ufc_se_nonce"] = nonce + 1
    fetch_stats.clear()
    st.rerun()

# Rank cards
ranked = fighters.sort_values("SE Rating", ascending=False).reset_index(drop=True)
st.subheader("🔥 Fighter Target Board")
st.caption("This is the pool-building view. Rank 1 = strongest single-entry target after salary, win equity, finish ceiling, value and projected ownership.")
cols = st.columns(4)
for i, r in ranked.iterrows():
    rank = i+1
    tier = tier_for(rank, float(r["SE Rating"]), float(r["pOwn%"]), float(r["Win %"]))
    css = {"CORE":"core","STRONG":"strong","LEVERAGE":"leverage","THIN":"thin","FADE":"fade"}[tier]
    pill = "pill-core" if tier in ("CORE","STRONG") else "pill-lev"
    odds = int(r["Moneyline"]) if pd.notna(r["Moneyline"]) else 0
    odds_txt = f"{odds:+d}" if odds else "—"
    html = f"""
    <div class="f-card tier-{css}">
      <div style="display:flex;justify-content:space-between;gap:8px">
        <div>
          <div class="f-rank">#{rank} · {tier}</div>
          <div class="f-name">{r['Name']}</div>
        </div>
        <div style="text-align:right">
          <div class="f-score">{r['SE Rating']:.0f}</div>
          <div class="small-muted">SE rating</div>
        </div>
      </div>
      <div class="f-meta">${int(r['Salary']):,} · {odds_txt} · vs {r['Opp']}</div>
      <div style="margin-top:7px">
        <span class="pill {pill}">{r['Win %']:.0f}% win</span>
        <span class="pill">{r['Finish %']:.0f}% finish</span>
        <span class="pill">{r['pOwn%']:.0f}% own</span>
      </div>
    </div>"""
    cols[i%4].markdown(html, unsafe_allow_html=True)

with st.expander("⚙️ Fighter Pool + ownership / finish overrides", expanded=False):
    edited = st.data_editor(
        editor, hide_index=True, use_container_width=True, height=620,
        column_order=["In","Lock","Name","Opp","Salary","Moneyline","pOwn%","Win %","Finish %","Projection","Ceiling","SE Rating","Fight"],
        disabled=["ID","Name","Opp","Salary","Win %","Projection","Ceiling","SE Rating","Fight"],
        column_config={
            "In": st.column_config.CheckboxColumn("In"),
            "Lock": st.column_config.CheckboxColumn("🔒"),
            "Salary": st.column_config.NumberColumn("Salary", format="$%d"),
            "Moneyline": st.column_config.NumberColumn("Odds", step=5),
            "pOwn%": st.column_config.NumberColumn("Own %", min_value=0.1, max_value=95.0, step=1.0, format="%.1f"),
            "Win %": st.column_config.NumberColumn("Win %", format="%.1f"),
            "Finish %": st.column_config.NumberColumn("Finish %", min_value=1.0, max_value=90.0, step=1.0, format="%.1f"),
            "Projection": st.column_config.NumberColumn("Mean", format="%.1f"),
            "Ceiling": st.column_config.NumberColumn("Ceiling", format="%.1f"),
            "SE Rating": st.column_config.NumberColumn("SE", format="%.0f"),
        },
        key="ufc_se_editor"
    )

st.session_state["ufc_se_prefs"] = {
    str(int(r["ID"])): {
        "In": bool(r["In"]), "Lock": bool(r["Lock"]),
        "pOwn%": float(r["pOwn%"]), "Finish %": float(r["Finish %"]),
        "Moneyline": float(r["Moneyline"]) if pd.notna(r["Moneyline"]) else np.nan,
    } for _, r in edited.iterrows()
}

# Rebuild model from editable odds, then preserve user's ownership / finish overrides.
base = fighters.drop(columns=["Win %","Finish %","Projection","Ceiling","pOwn%","Value","SE Rating"], errors="ignore")
for i, r in base.iterrows():
    er = edited.loc[edited["Name"] == r["Name"]]
    if len(er):
        base.at[i, "Moneyline"] = er.iloc[0]["Moneyline"]
modeled = build_model(base)
for i, r in modeled.iterrows():
    er = edited.loc[edited["Name"] == r["Name"]]
    if len(er):
        modeled.at[i, "pOwn%"] = float(er.iloc[0]["pOwn%"])
        modeled.at[i, "Finish %"] = float(er.iloc[0]["Finish %"])
fighters = modeled

st.markdown("### 🧠 What the single-entry engine is optimizing")
st.caption("One winner per fight · no opponent pairing · exact 1,189-entry field model · simulated win rate · top-1% rate · P99 ceiling · ownership-based duplicate pressure · no requirement to spend all $50K.")

if min_salary > max_salary:
    st.error("Minimum salary cannot exceed maximum salary.")
    st.stop()

if st.button("☢️ BUILD MY SINGLE-ENTRY LINEUP", type="primary", use_container_width=True):
    include = set(edited.loc[edited["In"], "ID"].astype(int))
    locked = set(edited.loc[edited["In"] & edited["Lock"], "ID"].astype(int))
    if len(locked) > 6:
        st.error("You can lock at most six fighters.")
        st.stop()
    seed = int(np.random.default_rng().integers(1, 2_000_000_000))
    with st.status("🥊 Building the 1,189-entry single-entry model...", expanded=True) as status:
        st.write("Enumerating legal six-fighter lineups...")
        cands = enumerate_candidates(
            fighters, include, locked, int(min_salary), int(max_salary),
            int(max_dogs), int(candidate_keep), seed
        )
        if not cands:
            status.update(label="No legal lineups", state="error")
            st.error("No lineups fit the current pool/salary rules.")
            st.stop()
        st.write(f"✅ {len(cands):,} high-quality candidate lineups retained")
        st.write(f"Simulating {int(n_sims):,} correlated fight-card outcomes...")
        sims = simulate_card(fighters, int(n_sims), seed+17)
        st.write(f"Building a simulated field of {int(field_size):,} entries and measuring first-place paths...")
        results = evaluate_candidates(cands, sims, fighters, int(field_size), seed)
        st.session_state["ufc_se_results"] = (results, cands, fighters, int(field_size), int(n_sims))
        status.update(label="✅ Single-entry build complete", state="complete", expanded=False)

if "ufc_se_results" in st.session_state:
    results, cands, rf, fs, ns = st.session_state["ufc_se_results"]
    st.divider()
    st.header("🏆 Best Single-Entry Builds")
    top = results.head(10).copy()

    best = top.iloc[0]
    best_c = cands[int(best["_candidate"])]
    best_names = lineup_names(best_c, rf)
    own_map = dict(zip(rf["Name"], rf["pOwn%"])); win_map = dict(zip(rf["Name"], rf["Win %"]))
    lev_names = sorted(best_names, key=lambda n: own_map.get(n, 99))[:2]
    favorites = sum(win_map.get(n, 0) >= 50 for n in best_names)

    st.markdown(f"""
    <div class="lineup-card">
      <div class="lu-rank">NUKE #1 · SINGLE-ENTRY RECOMMENDATION</div>
      <div class="lu-fighters">{' · '.join(best_names)}</div>
      <div class="small-muted">${int(best['Salary']):,} used · ${int(best['Left']):,} left · {favorites} favorites · leverage anchors: {', '.join(lev_names)}</div>
    </div>
    """, unsafe_allow_html=True)

    a,b,c,d = st.columns(4)
    a.metric("Simulated Win %", f"{best['Win %']:.2f}%")
    b.metric("Top 1% Rate", f"{best['Top 1% %']:.1f}%")
    c.metric("P99 Score", f"{best['P99']:.1f}")
    d.metric("Expected Dup", f"{best['Expected Dup']:.2f}")

    show = []
    for rank, r in top.reset_index(drop=True).iterrows():
        cnd = cands[int(r["_candidate"])]
        show.append({
            "#": rank+1,
            "Lineup": " · ".join(lineup_names(cnd, rf)),
            "Salary": int(r["Salary"]),
            "Left": int(r["Left"]),
            "Win %": round(float(r["Win %"]), 3),
            "Top 1% %": round(float(r["Top 1% %"]), 2),
            "P95": round(float(r["P95"]), 1),
            "P99": round(float(r["P99"]), 1),
            "Own Sum %": round(float(r["Own Sum %"]), 1),
            "Expected Dup": round(float(r["Expected Dup"]), 2),
            "Dogs": int(r["Underdogs"]),
            "SE Score": round(float(r["SE Score"]), 2),
        })
    st.dataframe(pd.DataFrame(show), hide_index=True, use_container_width=True, height=390)

    st.subheader("Why NUKE likes #1")
    reasons = []
    if best["Left"] >= 300:
        reasons.append(f"leaves ${int(best['Left']):,}, which can reduce exact duplication without forcing bad plays")
    if best["Expected Dup"] < 1:
        reasons.append("projects as a relatively low-duplication construction in this field size")
    if best["Low-Owned"] >= 1:
        reasons.append(f"contains {int(best['Low-Owned'])} lower-owned leverage piece(s) instead of an all-chalk six-pack")
    if best["Underdogs"] <= 2:
        reasons.append("keeps upset dependence controlled while still allowing tournament leverage")
    reasons.append("ranked best by simulated first-place rate first, with P99 ceiling and top-1% frequency as secondary signals")
    st.markdown(" • ".join(reasons) + ".")

    csv = dk_export_lineups(top, cands, rf, n=10)
    if csv is not None:
        st.download_button("⬇️ DOWNLOAD TOP 10 — DK FORMAT", csv, "NUKE_UFC_SE_TOP10.csv", "text/csv", type="primary", use_container_width=True)
    else:
        st.info("Lineup export requires a valid DraftKings fighter ID for every selected fighter.")

    st.caption("Model outputs are estimates, not guarantees. The objective is to maximize first-place paths in this specific contest structure, not to maximize median projection.")

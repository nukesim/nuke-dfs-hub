from pathlib import Path

p = Path('nuke_showdown_sim.py')
s = p.read_text(encoding='utf-8')

start = s.index('def generate_showdown_candidates(')
end = s.index('\ndef exposure_table(', start)

replacement = r'''def generate_showdown_candidates(players, max_candidates=12000, min_salary=42000, max_salary=SHOWDOWN_SALARY_CAP, seed=26):
    """Create a diverse legal Showdown candidate pool quickly using NumPy arrays."""
    rows = players.reset_index(drop=True)
    n = len(rows)
    if n < 6:
        return []

    rng = np.random.default_rng(int(seed) + 7919)
    base = np.array([_base_projection(r) for _, r in rows.iterrows()], dtype=np.float32)
    flex_salary = rows["FLEX Salary"].to_numpy(dtype=np.int32)
    cpt_salary = rows["CPT Salary"].to_numpy(dtype=np.int32)
    team_codes, _ = pd.factorize(rows["Team"].astype(str), sort=False)

    cpt_score = base + flex_salary.astype(np.float32) / 5000.0
    cpt_count = min(n, max(16, min(30, n)))
    cpt_pool = np.argsort(-cpt_score)[:cpt_count].astype(np.int32)

    flex_weight = np.maximum(base, 0.75) ** 1.15
    flex_weight = flex_weight / flex_weight.sum()

    target = int(max_candidates)
    minimum = int(min_salary)
    maximum = min(SHOWDOWN_SALARY_CAP, int(max_salary))
    seen = set()
    candidates = []

    # Tight salary windows can reject many random draws. Cap wasted work while still
    # giving the sampler ample room to fill normal 3k/6k/12k candidate requests.
    max_attempts = max(30000, target * 25)
    cpt_order = rng.permutation(cpt_pool).tolist()
    cpt_cursor = 0

    # Cache eligible arrays/probabilities for each Captain instead of rebuilding them.
    cached = {}
    all_idx = np.arange(n, dtype=np.int32)
    for cpt in cpt_pool:
        eligible = all_idx[all_idx != cpt]
        probs = flex_weight[eligible].astype(np.float64, copy=True)
        probs /= probs.sum()
        cached[int(cpt)] = (eligible, probs)

    for attempts in range(max_attempts):
        if len(candidates) >= target:
            break
        cpt = int(cpt_order[cpt_cursor % len(cpt_order)])
        cpt_cursor += 1
        if cpt_cursor % len(cpt_order) == 0:
            cpt_order = rng.permutation(cpt_pool).tolist()

        eligible, probs = cached[cpt]
        flex_arr = rng.choice(eligible, size=5, replace=False, p=probs)
        flex = tuple(sorted(map(int, flex_arr)))
        ident = (cpt, flex)
        if ident in seen:
            continue

        salary = int(cpt_salary[cpt] + flex_salary[flex_arr].sum())
        if salary < minimum or salary > maximum:
            continue

        inds = np.empty(6, dtype=np.int32)
        inds[0] = cpt
        inds[1:] = flex_arr
        if np.unique(team_codes[inds]).size < 2:
            continue

        seen.add(ident)
        candidates.append((cpt, flex, salary))

    return candidates


def evaluate_candidates(players, candidates, sims, scripts):
    """Score candidates in vectorized batches rather than one lineup at a time."""
    if not candidates:
        return pd.DataFrame()

    n_candidates = len(candidates)
    cpts = np.fromiter((int(x[0]) for x in candidates), dtype=np.int32, count=n_candidates)
    flexes = np.asarray([x[1] for x in candidates], dtype=np.int32)
    salaries = np.fromiter((int(x[2]) for x in candidates), dtype=np.int32, count=n_candidates)

    means = np.empty(n_candidates, dtype=np.float32)
    ceilings = np.empty(n_candidates, dtype=np.float32)
    p95s = np.empty(n_candidates, dtype=np.float32)
    top1s = np.empty(n_candidates, dtype=np.float32)
    script_values = {name: np.empty(n_candidates, dtype=np.float32) for name in SCRIPT_NAMES}
    script_masks = {name: np.asarray(scripts == name) for name in SCRIPT_NAMES}

    # 256 x 5,000 float32 scores is only ~5 MB, keeping memory modest on Streamlit Cloud.
    batch_size = 256
    for lo in range(0, n_candidates, batch_size):
        hi = min(n_candidates, lo + batch_size)
        bcpt = cpts[lo:hi]
        bflex = flexes[lo:hi]
        scores = 1.5 * sims[:, bcpt].T
        scores += sims[:, bflex].sum(axis=2).T

        means[lo:hi] = scores.mean(axis=1)
        qs = np.quantile(scores, [0.90, 0.95, 0.99], axis=1)
        ceilings[lo:hi] = qs[0]
        p95s[lo:hi] = qs[1]
        top1s[lo:hi] = qs[2]
        for name, mask in script_masks.items():
            if mask.any():
                script_values[name][lo:hi] = scores[:, mask].mean(axis=1)
            else:
                script_values[name][lo:hi] = 0.0

    data = {
        "_cpt": cpts,
        "_flex": [tuple(map(int, row)) for row in flexes],
        "Salary": salaries,
        "Mean": means,
        "Ceiling": ceilings,
        "P95": p95s,
        "Top 1% Score": top1s,
    }
    data.update(script_values)
    df = pd.DataFrame(data)
    for col in ["Mean", "Ceiling", "P95", "Top 1% Score"]:
        std = float(df[col].std())
        df[f"_{col}"] = (df[col] - df[col].mean()) / (std if std and not np.isnan(std) else 1.0)
    df["NUKE Score"] = 100 + 12 * (
        .25 * df["_Mean"] + .30 * df["_Ceiling"] + .20 * df["_P95"] + .25 * df["_Top 1% Score"]
    )
    return df.sort_values(["NUKE Score", "Top 1% Score"], ascending=False).reset_index(drop=True)


def _construction_label_fast(cpt, flex, team_values):
    inds = (int(cpt),) + tuple(map(int, flex))
    counts = Counter(team_values[i] for i in inds)
    ordered = counts.most_common()
    if not ordered:
        return "Unknown"
    if len(ordered) == 2 and ordered[0][1] == ordered[1][1]:
        return "3-3 Even"
    major_team, major_count = ordered[0]
    minor_count = ordered[1][1] if len(ordered) > 1 else 0
    return f"{major_team} {major_count}-{minor_count}"


def _construction_label(cpt, flex, players):
    teams = players.reset_index(drop=True)["Team"].astype(str).to_numpy()
    return _construction_label_fast(cpt, flex, teams)


def add_lineup_labels(results, players):
    if results.empty:
        return results
    rows = players.reset_index(drop=True)
    names = rows["Name"].astype(str).to_numpy()
    teams = rows["Team"].astype(str).to_numpy()
    out = results.copy()
    out.insert(0, "CPT", [names[int(i)] for i in out["_cpt"]])
    for k in range(5):
        out.insert(k + 1, f"FLEX{k+1}", [names[int(x[k])] for x in out["_flex"]])
    out.insert(6, "Construction", [
        _construction_label_fast(r["_cpt"], r["_flex"], teams) for _, r in out.iterrows()
    ])
    return out


def build_portfolio(results, players, count=20, max_player_pct=.75, max_cpt_pct=.35, player_mins=None, player_maxes=None, construction_mins=None, construction_maxes=None):
    if results.empty:
        return results
    target = max(1, int(count))
    player_mins = player_mins or {}
    player_maxes = player_maxes or {}
    construction_mins = construction_mins or {}
    construction_maxes = construction_maxes or {}

    global_player_max = max(1, int(np.floor(target * float(max_player_pct) + 1e-9)))
    global_cpt_max = max(1, int(np.floor(target * float(max_cpt_pct) + 1e-9)))
    min_counts = {i: int(np.ceil(target * max(0.0, min(1.0, float(player_mins.get(i, 0.0)))))) for i in range(len(players))}
    max_counts = {}
    for i in range(len(players)):
        personal = max(0.0, min(1.0, float(player_maxes.get(i, 1.0))))
        max_counts[i] = min(global_player_max, int(np.floor(target * personal + 1e-9)))

    construction_min_counts = {str(k): int(np.ceil(target * max(0.0, min(1.0, float(v))))) for k, v in construction_mins.items()}
    construction_max_counts = {str(k): int(np.floor(target * max(0.0, min(1.0, float(v))) + 1e-9)) for k, v in construction_maxes.items()}

    player_counts = Counter(); cpt_counts = Counter(); construction_counts = Counter()
    chosen = []; used = set()
    band = results.head(min(len(results), 6000)).reset_index(drop=True)
    teams = players.reset_index(drop=True)["Team"].astype(str).to_numpy()

    # Precompute lineup membership and construction once instead of rebuilding from pandas
    # on every portfolio-selection pass.
    pre = []
    for ridx, r in band.iterrows():
        cpt = int(r["_cpt"])
        flex = tuple(map(int, r["_flex"]))
        inds = (cpt,) + flex
        construction = _construction_label_fast(cpt, flex, teams)
        pre.append((ridx, cpt, inds, construction, float(r.get("NUKE Score", 0.0))))

    for _ in range(target):
        best_idx = None; best_value = None; best_meta = None
        for ridx, cpt, inds, construction, score in pre:
            if ridx in used: continue
            if cpt_counts[cpt] >= global_cpt_max: continue
            if any(player_counts[i] >= max_counts.get(i, global_player_max) for i in inds): continue
            if construction in construction_max_counts and construction_counts[construction] >= construction_max_counts[construction]: continue

            deficit_bonus = sum(max(0, min_counts.get(i, 0) - player_counts[i]) * 1000.0 for i in inds)
            deficit_bonus += max(0, construction_min_counts.get(construction, 0) - construction_counts[construction]) * 1500.0
            value = deficit_bonus + score
            if best_value is None or value > best_value:
                best_value = value; best_idx = ridx; best_meta = (cpt, inds, construction)

        if best_idx is None:
            break
        chosen.append(band.iloc[best_idx])
        used.add(best_idx)
        cpt, inds, construction = best_meta
        cpt_counts[cpt] += 1
        player_counts.update(inds)
        construction_counts[construction] += 1

    return pd.DataFrame(chosen).reset_index(drop=True) if chosen else results.iloc[0:0].copy()
'''

s = s[:start] + replacement + s[end:]
p.write_text(s, encoding='utf-8')
print('optimized Showdown hot loops')

import math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

from nuke_nav import render_nav

st.set_page_config(page_title="NUKE Contest Fill Tracker", page_icon="📈", layout="wide")
render_nav()

TZ = ZoneInfo("America/Chicago")
DEFAULT_NAME = "Double Dribble"
DEFAULT_CAPACITY = 37_500
DEFAULT_ENTRANTS = 22_584
DEFAULT_ENTRY_FEE = 15.0
DEFAULT_CLOSE_DATE = date(2026, 10, 20)
DEFAULT_CLOSE_TIME = time(12, 23)
SIMS = 20_000

st.markdown(
    """
    <style>
    .block-container{padding-top:.8rem;max-width:1600px}
    .fill-hero{border:1px solid rgba(255,255,255,.10);border-radius:18px;padding:16px 18px;
      background:linear-gradient(135deg,rgba(25,195,125,.08),rgba(255,255,255,.018));margin-bottom:12px}
    .fill-kicker{font-size:.70rem;font-weight:1000;letter-spacing:.13em;color:#19c37d;text-transform:uppercase}
    .fill-title{font-size:2.0rem;font-weight:1000;letter-spacing:-.04em;margin-top:3px}
    .fill-sub{opacity:.68;font-size:.9rem;margin-top:2px}
    .signal{border:1px solid rgba(255,255,255,.09);border-radius:14px;padding:10px 12px;background:rgba(255,255,255,.018)}
    .signal-label{font-size:.66rem;opacity:.55;font-weight:900;text-transform:uppercase;letter-spacing:.08em}
    .signal-value{font-size:1.35rem;font-weight:1000;margin-top:3px}
    .good{color:#57d99a}.warn{color:#f2c94c}.bad{color:#ff6b6b}
    </style>
    """,
    unsafe_allow_html=True,
)


def fmt_int(x):
    try:
        return f"{int(round(float(x))):,}"
    except Exception:
        return "—"


def fmt_rate(x, unit="/day"):
    try:
        if not np.isfinite(float(x)):
            return "—"
        return f"{float(x):,.0f}{unit}"
    except Exception:
        return "—"


def logistic(x):
    return 1.0 / (1.0 + math.exp(-float(np.clip(x, -30, 30))))


def late_factor(hours_remaining, strength, half_life_hours=48.0):
    """Rate multiplier that ramps as the contest approaches lock."""
    h = np.maximum(np.asarray(hours_remaining, dtype=float), 0.0)
    return 1.0 + float(strength) * np.exp(-h / float(half_life_hours))


def prep_snapshots(df, now_dt, current_entrants):
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["timestamp", "entrants"])
    z = df.copy()
    if "timestamp" not in z.columns or "entrants" not in z.columns:
        return pd.DataFrame(columns=["timestamp", "entrants"])
    z["timestamp"] = pd.to_datetime(z["timestamp"], errors="coerce")
    z["entrants"] = pd.to_numeric(z["entrants"], errors="coerce")
    z = z.dropna(subset=["timestamp", "entrants"]).sort_values("timestamp")
    z = z[z["entrants"] >= 0].drop_duplicates("timestamp", keep="last")
    if not z.empty:
        try:
            z["timestamp"] = z["timestamp"].dt.tz_localize(None)
        except TypeError:
            z["timestamp"] = z["timestamp"].dt.tz_convert(TZ).dt.tz_localize(None)
    return z.reset_index(drop=True)


def observed_hourly_rate(snapshots, now_dt, current_entrants):
    """Recency-weighted pace from valid, increasing snapshot intervals."""
    if snapshots is None or len(snapshots) == 0:
        return np.nan, pd.DataFrame()

    z = snapshots.copy()
    now_naive = now_dt.replace(tzinfo=None)
    if z.empty or abs((now_naive - z.iloc[-1]["timestamp"]).total_seconds()) > 60:
        z = pd.concat(
            [z, pd.DataFrame([{"timestamp": now_naive, "entrants": current_entrants}])],
            ignore_index=True,
        ).sort_values("timestamp")
    else:
        z.loc[z.index[-1], "entrants"] = current_entrants

    z["prev_t"] = z["timestamp"].shift(1)
    z["prev_e"] = z["entrants"].shift(1)
    z["hours"] = (z["timestamp"] - z["prev_t"]).dt.total_seconds() / 3600.0
    z["adds"] = z["entrants"] - z["prev_e"]
    iv = z[(z["hours"] >= 0.5) & (z["adds"] >= 0)].copy()
    if iv.empty:
        return np.nan, iv

    iv["rate_hr"] = iv["adds"] / iv["hours"]
    age_h = (now_naive - iv["timestamp"]).dt.total_seconds().clip(lower=0) / 3600.0
    iv["weight"] = np.exp(-age_h / 72.0) * np.sqrt(np.minimum(iv["hours"], 48.0))
    rate = float(np.average(iv["rate_hr"], weights=iv["weight"]))
    return rate, iv


def model_probability(fill_pct, days_left, pace_ratio, confidence_n):
    """Transparent heuristic anchor, used as a sanity check next to Monte Carlo."""
    fill = float(np.clip(fill_pct, 0, 1))
    d = max(float(days_left), 0.02)
    pr = float(np.clip(pace_ratio, 0.05, 4.0))
    z = -2.15 + 3.35 * fill + 1.60 * math.log(pr + 0.35) + 0.38 * math.log(8.0 / (d + 1.0))
    if confidence_n <= 0:
        z *= 0.70
    elif confidence_n == 1:
        z *= 0.85
    return logistic(z)


def simulate_fill(current, capacity, hours_left, base_rate_hr, surge_strength, volatility, seed=20261013):
    if current >= capacity:
        return 1.0, np.full(SIMS, capacity, dtype=int), pd.DataFrame()
    if hours_left <= 0:
        finals = np.full(SIMS, current, dtype=int)
        return 0.0, finals, pd.DataFrame()

    rng = np.random.default_rng(seed)
    step = 6.0
    n_steps = max(1, int(math.ceil(hours_left / step)))
    elapsed = np.arange(1, n_steps + 1) * step
    rem = np.maximum(hours_left - elapsed, 0.0)
    step_hours = np.minimum(step, np.maximum(hours_left - np.arange(n_steps) * step, 0.0))

    persistent = rng.lognormal(mean=-0.5 * volatility**2, sigma=volatility, size=SIMS)
    surge_draw = np.clip(rng.normal(surge_strength, max(0.12, surge_strength * 0.20), size=SIMS), 0.0, 4.0)
    totals = np.full(SIMS, int(current), dtype=np.int64)

    track_idx = np.unique(np.linspace(0, n_steps - 1, min(n_steps, 30)).astype(int))
    track_rows = []

    for i in range(n_steps):
        lf = 1.0 + surge_draw * math.exp(-float(rem[i]) / 48.0)
        local_noise = rng.lognormal(mean=-0.5 * 0.16**2, sigma=0.16, size=SIMS)
        lam = np.maximum(base_rate_hr * lf * persistent * local_noise * float(step_hours[i]), 0.0)
        adds = rng.poisson(lam)
        totals = np.minimum(capacity, totals + adds)
        if i in track_idx:
            q10, q50, q90 = np.quantile(totals, [0.10, 0.50, 0.90])
            track_rows.append(
                {
                    "hours_from_now": float(min(elapsed[i], hours_left)),
                    "P10": int(q10),
                    "Median": int(q50),
                    "P90": int(q90),
                }
            )

    return float(np.mean(totals >= capacity)), totals, pd.DataFrame(track_rows)


now = datetime.now(TZ)

st.markdown(
    """
    <div class="fill-hero">
      <div class="fill-kicker">NUKE • Tournament Intelligence</div>
      <div class="fill-title">Contest Fill Tracker</div>
      <div class="fill-sub">Estimate sellout odds, required pace, late-entry surge, and final field size. Add snapshots over time and the model replaces guesswork with observed pace.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Contest setup")
    contest_name = st.text_input("Contest", DEFAULT_NAME)
    entry_fee = st.number_input("Entry fee ($)", min_value=0.0, value=DEFAULT_ENTRY_FEE, step=1.0)
    capacity = int(st.number_input("Max entrants", min_value=2, value=DEFAULT_CAPACITY, step=100))
    current = int(st.number_input("Current entrants", min_value=0, max_value=capacity, value=min(DEFAULT_ENTRANTS, capacity), step=1))
    close_d = st.date_input("Closes on", value=DEFAULT_CLOSE_DATE)
    close_t = st.time_input("Close time (Central)", value=DEFAULT_CLOSE_TIME)

    st.divider()
    st.markdown("### Model controls")
    manual_24h = st.number_input(
        "Known entries added in last 24h",
        min_value=0,
        value=0,
        step=25,
        help="Optional. Leave at 0 if unknown. Snapshot history takes priority once it has enough data.",
    )
    surge_strength = st.slider(
        "Late-entry surge",
        min_value=0.0,
        max_value=3.0,
        value=1.35,
        step=0.05,
        help="1.35 means the final-hour arrival rate can be roughly 2.35× the underlying base pace.",
    )
    volatility = st.slider(
        "Forecast volatility",
        min_value=0.10,
        max_value=0.60,
        value=0.28,
        step=0.02,
        help="Higher values create a wider range of possible final field sizes.",
    )

close_dt = datetime.combine(close_d, close_t, tzinfo=TZ)
hours_left = max((close_dt - now).total_seconds() / 3600.0, 0.0)
days_left = hours_left / 24.0
fill = current / capacity if capacity else 0.0
left = max(capacity - current, 0)
required_hr = (left / hours_left) if hours_left > 0 else np.inf
required_day = required_hr * 24.0 if np.isfinite(required_hr) else np.inf

if "fill_snapshots" not in st.session_state:
    st.session_state["fill_snapshots"] = pd.DataFrame(
        [{"timestamp": now.replace(tzinfo=None).replace(microsecond=0), "entrants": current}]
    )

st.subheader(contest_name)
summary_cols = st.columns(6)
summary_cols[0].metric("Filled", f"{fill:.1%}")
summary_cols[1].metric("Current field", fmt_int(current))
summary_cols[2].metric("Entries left", fmt_int(left))
summary_cols[3].metric("Time left", f"{days_left:.2f} days")
summary_cols[4].metric("Required / day", fmt_rate(required_day))
summary_cols[5].metric("Entry fee", f"${entry_fee:,.0f}")

st.markdown("### Snapshot history")
st.caption("Record the field size whenever you check the contest. Two or more timestamps let NUKE measure actual entry velocity instead of relying on a prior.")

edited = st.data_editor(
    st.session_state["fill_snapshots"],
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "timestamp": st.column_config.DatetimeColumn("Timestamp (Central)", format="MM/DD/YYYY hh:mm a"),
        "entrants": st.column_config.NumberColumn("Entrants", min_value=0, step=1, format="%d"),
    },
    key="fill_snapshot_editor",
)

b1, b2, _ = st.columns([1, 1, 4])
if b1.button("➕ Add current snapshot", use_container_width=True):
    z = prep_snapshots(edited, now, current)
    z = pd.concat(
        [z, pd.DataFrame([{"timestamp": now.replace(tzinfo=None).replace(microsecond=0), "entrants": current}])],
        ignore_index=True,
    ).drop_duplicates("timestamp", keep="last").sort_values("timestamp")
    st.session_state["fill_snapshots"] = z[["timestamp", "entrants"]].reset_index(drop=True)
    st.session_state.pop("fill_snapshot_editor", None)
    st.rerun()
if b2.button("🧹 Reset snapshots", use_container_width=True):
    st.session_state["fill_snapshots"] = pd.DataFrame(
        [{"timestamp": now.replace(tzinfo=None).replace(microsecond=0), "entrants": current}]
    )
    st.session_state.pop("fill_snapshot_editor", None)
    st.rerun()

snapshots = prep_snapshots(edited, now, current)
st.session_state["fill_snapshots"] = snapshots[["timestamp", "entrants"]].copy() if not snapshots.empty else pd.DataFrame(columns=["timestamp", "entrants"])
obs_rate_hr, interval_df = observed_hourly_rate(snapshots, now, current)

if np.isfinite(obs_rate_hr) and len(interval_df) >= 1:
    current_rate_hr = float(obs_rate_hr)
    pace_source = "Observed snapshots"
    confidence_n = len(interval_df)
elif manual_24h > 0:
    current_rate_hr = float(manual_24h) / 24.0
    pace_source = "Manual last-24h pace"
    confidence_n = 1
else:
    current_rate_hr = required_hr * 0.84 if np.isfinite(required_hr) else 0.0
    pace_source = "Heuristic prior (no pace history yet)"
    confidence_n = 0

current_late = float(late_factor(hours_left, surge_strength)) if hours_left > 0 else 1.0
base_rate_hr = current_rate_hr / max(current_late, 1e-9)
pace_ratio = current_rate_hr / required_hr if required_hr > 0 and np.isfinite(required_hr) else np.inf

mc_prob, finals, track = simulate_fill(
    current=current,
    capacity=capacity,
    hours_left=hours_left,
    base_rate_hr=max(base_rate_hr, 0.0),
    surge_strength=surge_strength,
    volatility=volatility,
)
anchor_prob = model_probability(fill, days_left, pace_ratio if np.isfinite(pace_ratio) else 4.0, confidence_n)
anchor_weight = 0.38 if confidence_n == 0 else (0.22 if confidence_n == 1 else 0.10)
fill_prob = (1.0 - anchor_weight) * mc_prob + anchor_weight * anchor_prob

q10, q50, q90 = np.quantile(finals, [0.10, 0.50, 0.90]) if len(finals) else (current, current, current)
median_fill = min(q50 / capacity, 1.0)
projected_shortfall = max(capacity - q50, 0)

st.markdown("### Fill forecast")
prob_pct = fill_prob * 100.0
if prob_pct >= 80:
    verdict, cls = "LIKELY TO FILL", "good"
elif prob_pct >= 55:
    verdict, cls = "LEAN FILL", "warn"
elif prob_pct >= 35:
    verdict, cls = "TRUE SWEAT", "warn"
else:
    verdict, cls = "UNLIKELY TO FILL", "bad"

cards = st.columns(5)
card_data = [
    ("Sellout probability", f"{prob_pct:.0f}%", cls),
    ("Model verdict", verdict, cls),
    ("Current pace", fmt_rate(current_rate_hr * 24.0), ""),
    ("Pace vs required", f"{pace_ratio:.2f}×" if np.isfinite(pace_ratio) else "—", "good" if pace_ratio >= 1 else "warn"),
    ("Median final field", fmt_int(q50), "good" if median_fill >= .98 else ""),
]
for c, (lab, val, klass) in zip(cards, card_data):
    c.markdown(
        f'<div class="signal"><div class="signal-label">{lab}</div><div class="signal-value {klass}">{val}</div></div>',
        unsafe_allow_html=True,
    )

st.caption(
    f"Pace source: **{pace_source}**. Forecast range (10th–90th percentile): **{fmt_int(q10)}–{fmt_int(q90)}** entrants. "
    + ("Snapshot confidence improves as you record more observations." if confidence_n < 2 else f"Built from {confidence_n} valid snapshot intervals.")
)

left_col, right_col = st.columns([1.35, 1.0])
with left_col:
    st.markdown("#### Projected field path")
    if not track.empty:
        chart = track.copy()
        chart["date"] = [now + timedelta(hours=float(h)) for h in chart["hours_from_now"]]
        chart = chart.set_index("date")[["P10", "Median", "P90"]]
        st.line_chart(chart, use_container_width=True)
    else:
        st.info("No time remains before close, so there is no future path to project.")

with right_col:
    st.markdown("#### What has to happen")
    target_24h = required_day
    target_6h = required_hr * 6.0 if np.isfinite(required_hr) else np.inf
    projected_adds = max(q50 - current, 0)
    rows = [
        ["Needed to sell out", fmt_int(left)],
        ["Needed every 24h", fmt_int(target_24h)],
        ["Needed every 6h", fmt_int(target_6h)],
        ["Model median adds", fmt_int(projected_adds)],
        ["Median shortfall", fmt_int(projected_shortfall)],
        ["Current late-surge multiplier", f"{current_late:.2f}×"],
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Signal", "Value"]), hide_index=True, use_container_width=True)

st.markdown("### Milestone board")
milestones = []
for pct in [0.70, 0.80, 0.90, 0.95, 1.00]:
    target = int(math.ceil(capacity * pct))
    need = max(target - current, 0)
    req_d = need / max(days_left, 1e-9) if days_left > 0 else (0 if need == 0 else np.inf)
    if current_rate_hr > 0 and need > 0:
        eta_hours_flat = need / current_rate_hr
        eta = now + timedelta(hours=eta_hours_flat)
        eta_txt = eta.strftime("%a %m/%d %I:%M %p")
    elif need == 0:
        eta_txt = "Already reached"
    else:
        eta_txt = "—"
    milestones.append(
        {
            "Milestone": f"{int(pct*100)}%",
            "Field target": target,
            "Still needed": need,
            "Required / day": None if not np.isfinite(req_d) else round(req_d),
            "Flat-pace ETA": eta_txt,
        }
    )
st.dataframe(pd.DataFrame(milestones), hide_index=True, use_container_width=True)

if len(interval_df):
    with st.expander("Observed pace detail", expanded=False):
        show = interval_df[["prev_t", "timestamp", "hours", "adds", "rate_hr"]].copy()
        show.columns = ["From", "To", "Hours", "Entries added", "Entries / hour"]
        show["Hours"] = show["Hours"].round(2)
        show["Entries / hour"] = show["Entries / hour"].round(1)
        st.dataframe(show, hide_index=True, use_container_width=True)

with st.expander("How the model works", expanded=False):
    st.markdown(
        """
        **NUKE Fill Tracker is a forecasting model, not a guarantee.** It combines the contest's current fill percentage, time remaining, the pace required to sell out, observed snapshot velocity (when available), and a configurable late-entry surge. It then runs 20,000 simulated field-growth paths and reports how often the contest reaches capacity.

        With only one snapshot, the probability is intentionally tagged to a **heuristic prior**, because there is no real pace history yet. Record another field count later today and again tomorrow; the forecast will begin using the actual entry rate and become materially more useful.
        """
    )

csv_out = snapshots.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Download snapshots CSV",
    data=csv_out,
    file_name=f"{contest_name.lower().replace(' ', '_')}_fill_snapshots.csv",
    mime="text/csv",
)

# NUKE NFL DFS HUB v20 — Correlation Builder

## 🚀 Live App
**Open NUKE DFS Hub:** https://nuke-dfs-app.streamlit.app/

The Streamlit deployment tracks the `main` branch of this repository, so merged updates should appear in the live app after Streamlit redeploys.

## New in BUILD
- Multi-row player selection.
- Select two WRs, three RB/WR/TE options, etc. and add them in one action.
- Players already used in the active lineup are hidden and cannot be selected again.
- Selected players are automatically placed into the next legal DK roster slots.

## Correlation Map
Every active lineup card now displays easy-to-read correlation badges:
- `QB+2 BUF`
- `BRING-BACK HOU x1`
- `GAME BUF-HOU 4-2`
- `DET x2`

This exposes QB stacks, bring-backs, same-game concentration, and same-team correlation without requiring you to scan abbreviations manually.

## Game Portfolio Map
The game board can now sort by:
- Most stacked
- Most saved lineup appearances
- Most pool players
- Highest game total
- Most 4+ stacks

Game-stack structures are larger and easier to read.

## Team Stacking / Exposure Ranking
A new expandable table can sort teams by:
- QB Stack LU
- 3+ Team LU
- 2+ Team LU
- Saved LU
- Pool
- Players Used

Saved Lineup preview cards also include the Correlation Map badges.

## NBA Classic simulator

Open **NBA Sim** from the NUKE sidebar. The default slate is the October 20, 2026
DraftKings NBA Classic salary CSV; upload a fresh DK file for subsequent slates.

- Refresh ESPN NBA injuries, game lines, and the publicly listed expected/confirmed
  starting fives from RotoWire; the NBA page checks feeds every five minutes while open.
- Model 240 minutes per NBA team, with role-aware rotation weights, injury exclusions,
  optional Q/doubtful scenarios, a manual minutes override, and historical ESPN
  player scoring rates. The first 2026-27 slate uses the 2025-26 statistical prior.
- Display projection, ceiling, 20+ fantasy-point frequency, 6x salary frequency,
  minutes, value and **model-estimated** ownership on the player lab.
- Build up to 150 unique GPP lineups via a legal DraftKings position/salary integer
  optimizer, with contest size, max-team, minimum salary and exposure controls.
- Evaluate lineups with correlated slate simulations, synthetic field benchmarks,
  a high-ceiling/low-duplication GPP score, and player exposure bars. Export the
  eight DK ID columns: `PG,SG,SF,PF,C,G,F,UTIL`.

**Important limitations:** Starting lineups stay marked *expected* until explicitly
confirmed by the source. Feed failures are shown; existing DK statuses remain a
conservative fallback. Missing ESPN history is labeled as a DK-average fallback.
Ownership and simulated field-beat percentages are heuristic research estimates,
not real DraftKings contest ownership or calibrated winning probabilities. The
CSV export does not implement locked-player late swaps on already-entered lineups.

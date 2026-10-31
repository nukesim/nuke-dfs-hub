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

## NFL Strategy Studio

Open **NFL Sim → Strategy Studio** next to Player Pool. Rules use the active pool and each platform keeps a separate rulebook.

1. Start with **QB + receiver**, **QB + bring-back**, or **Limit a combination**, or create a custom rule.
2. Choose an optional anchor and check the other players in the group. Search the whole slate to make cross-game groups. The anchor is separate from the group's counts.
3. Set minimum / maximum group players. **Every** means 100%; **Most** means at least 75%; **Custom** lets you choose another minimum percentage. The preview spells out the rule before saving.
4. Run NUKE SIM to create compatible candidates, or **Apply rulebook to portfolio** to select from an existing run using sidebar size/caps and saved Player Takes. Rebuilding through Portfolio Manager also enforces the rulebook.
5. Review **Portfolio check** for triggered-lineup counts, matching counts, required counts and actual percentages. Conditional rules never force anchor exposure: use Player Takes minimums for that. No anchor lineups is labeled **Not used**.

The Game map shows saved rule relationships. After selection, bubble size grows with measured portfolio exposure; it is not projected ownership or an estimated correlation coefficient. Drafts and active rules are not recommendations to play particular players.

Every rules constrain individual candidates. Percentage rules constrain the selected portfolio, with counts rounded upward (75% of three requires three). Exact selection honors player/QB/team/game caps, player minimums and maximum overlap. Infeasible or timed-out selections produce an explanation instead of substituting a noncompliant portfolio. Constrained candidate construction has a 45-second supplement budget and may return a smaller candidate pool; this is reported. Portfolio exports are verified; ranked candidate exports are explicitly labeled as research views that may not satisfy the rulebook.

Workspace saves preserve rulebooks. Rules use official player IDs so reordering cannot retarget them. On a new slate, review, edit or pause rules with unavailable anchors or insufficient active group members. Healthy-player status and all news/projection limitations elsewhere in the app still apply.


# NUKE NFL DFS HUB v14 — Market Model

## Major changes

### Backup-QB ownership fix
Estimated ownership now uses a hard QB role gate.

A QB identified as a backup by the latest nflverse depth chart gets **0.0% estimated field ownership** unless current sportsbook passing props indicate that he is actually expected to start.

Very-low-projection QBs are also removed from the ownership pool.

### Prop-based fantasy projection
The PLAYER MODEL now supports current NFL player props through PropLine.

Prop markets are converted directly into DraftKings expectation:

- Passing yards × 0.04
- Passing TD expectation × 4
- Rushing yards × 0.10
- Receptions × 1
- Receiving yards × 0.10
- Anytime TD probability × 6
- estimated 300-yard passing / 100-yard rushing / 100-yard receiving bonuses

When several prop markets exist for a player, the market-derived projection receives the majority of the Median projection weight.

Historical nflverse usage remains in the model as a stabilizer.

### Depth chart role
The model now attempts to load the latest 2026 nflverse depth-chart release and displays:

- STARTER
- ROTATION
- BACKUP
- UNKNOWN

### Free API integration
PropLine currently advertises a free tier with 1,000 requests/day.

In PLAYER MODEL:
1. Paste your PropLine API key.
2. Click FETCH NFL PROPS.
3. Click LOAD / REFRESH MODEL.

The API key is held in Streamlit Session State and is not written to the repo or workspace file.

NFL regular-season player props activate when books begin posting them.

## Existing features retained
Player pool, game-by-game analysis, QB plan, 1–4 lineup builder, FLEX late-swap optimizer, saved lineups, exposure, combo exposure, and DraftKings export all remain.

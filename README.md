# NUKE NFL DFS HUB v15 — Free Player Model

No paid projections. No ownership subscription. No API key.

## Player Model

The PLAYER MODEL now uses only free / already-available inputs:

- nflverse historical weekly player stats
- nflverse depth chart role
- recent DraftKings fantasy scoring
- recent opportunity / workload trend
- DraftKings salary
- game total
- implied team total
- spread / game environment
- optional manual role adjustment

Outputs include:

- Median
- Floor
- Ceiling
- Value
- Boom %
- Estimated Field %
- Small Field score
- Large Field score
- Confidence
- Depth Role
- Role Trend
- Historical Games

## Backup QB ownership protection

If the latest nflverse depth chart identifies a QB as a BACKUP:

- projected median is heavily suppressed
- ceiling is capped
- Estimated Field % is forced to 0.0%

Very-low-projection QBs are also excluded from the QB ownership pool.

## Estimated Field %

This remains a heuristic, not a paid ownership feed.

It distributes likely field attention using:

- projection strength
- salary
- value
- game environment
- position
- depth-chart role

## Injury / role changes

Use **Player Role Adjustment** when news changes a player's expected workload faster than historical data can reflect it.

Example:
- backup RB becomes starter
- add a positive role adjustment
- rebuild model

## Existing Hub features remain

- Player Pool
- Game-by-game slate analysis
- QB Plan
- 1–4 lineup multi-builder
- FLEX late-swap optimization
- Saved Lineups
- Exposure & Combos
- DraftKings CSV export
- Workspace save/load

## Deployment

Replace `app.py`, `requirements.txt`, and `README.md` in the GitHub repo.

Streamlit Community Cloud will redeploy automatically.

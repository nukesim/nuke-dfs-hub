# NUKE NFL DFS HUB v13 — Free Player Model

This deployment-ready version adds a free projection/player-model layer to the existing NUKE Hub.

## Player Model
After uploading a DraftKings slate, open **PLAYER MODEL** and click **LOAD / REFRESH MODEL**.

The model combines:
- free historical weekly NFL player stats from nflverse
- recent DraftKings fantasy scoring
- recent opportunity / role trend
- DraftKings salary
- game total
- implied team total
- spread / game environment
- optional manual role adjustments

Outputs:
- Median projection
- Floor
- Ceiling
- Value
- Boom %
- Heuristic estimated ownership / popularity
- Small Field score
- Large Field score
- Model confidence

### Important
`Est Own` is intentionally labeled as a heuristic. It is not presented as the equivalent of a paid ownership feed.

## Small vs Large Field
Fantasy-point projections remain the same.

Small Field score emphasizes:
- median
- ceiling
- value
- confidence

Large Field score emphasizes:
- ceiling
- boom probability
- leverage
- game environment

## Injury / role adjustments
Use **Player Role Adjustment** for information the historical data does not yet reflect.

Example:
A cheap backup RB becomes the starter:
- select the player
- add a positive role adjustment
- rebuild automatically

## Performance
Historical data is not downloaded during normal lineup-building clicks.

The app fetches it only when you click **LOAD / REFRESH MODEL**, and Streamlit caches the free history for six hours.

## Free data
Historical weekly player stats are loaded from the nflverse public player-stats releases.

## Hosting
This package remains ready for Streamlit Community Cloud.

Replace the existing GitHub repo files with the v13 files and Streamlit will redeploy automatically.

# Deploy NUKE DFS HUB free with Streamlit Community Cloud

## Step 1 — GitHub

Create a new GitHub repository. Suggested name:

`nuke-dfs-hub`

For the easiest first deployment, make it **Public**.

Upload the CONTENTS of this folder to the root of the repository:

- `app.py`
- `requirements.txt`
- `gametotals.xlsx`
- `README.md`
- `DEPLOY.md`
- `.gitignore`
- `.streamlit/config.toml`

Do not upload `NUKE_DFS_HUB_v12_DEPLOY_READY.zip` itself into the repository.

## Step 2 — Streamlit Community Cloud

Sign in to Streamlit Community Cloud with GitHub.

Create a new app and select:

- Repository: `nuke-dfs-hub`
- Branch: `main`
- Main file path: `app.py`

Then click **Deploy**.

## Step 3 — Share

Your hosted app will get a public address ending in:

`.streamlit.app`

Send that link to your friends. They only need a browser.

## Updating the app later

When we make v13, v14, etc., replace `app.py` in GitHub and commit the change.

Streamlit Community Cloud watches the GitHub repo and redeploys when the files change.

## Updating betting lines

The hosted app uses the `gametotals.xlsx` stored in the GitHub repository.

To publish updated lines:

1. Update `gametotals.xlsx` locally.
2. Replace the GitHub copy.
3. Commit the change.
4. Streamlit redeploys automatically.

The app also supports a temporary uploaded totals workbook during an individual session.

## Your friend's data

DraftKings CSV uploads and Streamlit Session State are browser-session-specific.

One user does not automatically share an active lineup-building session with another user.

For longer-term work, use the app's workspace JSON download and restore feature.

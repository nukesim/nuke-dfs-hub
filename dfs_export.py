from dk_export import build_lineup_only_csv as _dk_build, fill_entries_csv as _dk_fill, add_dk_roster_columns as _dk_add_roster_columns
from fd_export import build_fd_lineup_only_csv as _fd_build, fill_fd_entries_csv as _fd_fill, add_fd_roster_columns as _fd_add_roster_columns
from dfs_platform import normalize_site


def _site(players, site=None):
    if site is not None:
        return normalize_site(site)
    return normalize_site(getattr(players, "attrs", {}).get("site", "DK"))


def build_lineup_only_csv(players, results, limit=None, site=None):
    return _fd_build(players, results, limit=limit) if _site(players, site) == "FD" else _dk_build(players, results, limit=limit)


def fill_entries_csv(upload_bytes, players, results, limit=None, site=None):
    if _site(players, site) == "FD":
        return _fd_fill(upload_bytes, players, results, limit=limit)
    return _dk_fill(upload_bytes, players, results, limit=limit)


def add_roster_columns(players, results, site=None):
    """Add the correct platform roster columns without shadowing the imported DK helper."""
    return _fd_add_roster_columns(players, results) if _site(players, site) == "FD" else _dk_add_roster_columns(players, results)


# Backward-compatible name used by the existing SIM UI. Despite the historical
# function name, dispatch to the selected platform via players.attrs['site'].
def add_dk_roster_columns(players, results, include_ids=True):
    return add_roster_columns(players, results)

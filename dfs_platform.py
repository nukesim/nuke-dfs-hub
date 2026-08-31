from dataclasses import dataclass

DK = "DK"
FD = "FD"


@dataclass(frozen=True)
class PlatformConfig:
    code: str
    name: str
    salary_cap: int
    default_min_salary: int
    min_salary_input: int
    max_salary_input: int
    reception_points: float
    yardage_bonuses: bool
    defense_slot: str


PLATFORMS = {
    DK: PlatformConfig(
        code=DK,
        name="DraftKings",
        salary_cap=50000,
        default_min_salary=49400,
        min_salary_input=45000,
        max_salary_input=50000,
        reception_points=1.0,
        yardage_bonuses=True,
        defense_slot="DST",
    ),
    FD: PlatformConfig(
        code=FD,
        name="FanDuel",
        salary_cap=60000,
        default_min_salary=59400,
        min_salary_input=54000,
        max_salary_input=60000,
        reception_points=0.5,
        yardage_bonuses=False,
        defense_slot="D",
    ),
}


def normalize_site(site):
    s = str(site or DK).strip().upper()
    if s in {"FANDUEL", "FD"}:
        return FD
    return DK


def get_platform(site=DK):
    return PLATFORMS[normalize_site(site)]


def platform_label(site=DK):
    return get_platform(site).name


def detect_salary_site(df):
    cols = {str(c).strip().lower() for c in getattr(df, "columns", [])}
    if "nickname" in cols or ("first name" in cols and "last name" in cols and "fppg" in cols):
        return FD
    if "name + id" in cols or "roster position" in cols or "teamabbrev" in cols:
        return DK
    return None


def player_name_series(df):
    """Return the best available player-name column for either site's salary CSV."""
    for col in ["Name", "name", "Nickname", "nickname", "Player", "player", "Name + ID"]:
        if col in df.columns:
            return df[col].fillna("").astype(str)
    first = next((c for c in ["First Name", "First", "first_name"] if c in df.columns), None)
    last = next((c for c in ["Last Name", "Last", "last_name"] if c in df.columns), None)
    if first or last:
        a = df[first].fillna("").astype(str) if first else ""
        b = df[last].fillna("").astype(str) if last else ""
        return (a + " " + b).str.strip()
    return None

# smogon_utils.py
import re
import requests
from typing import Dict, Tuple, Set

USAGE_BASE = "https://www.smogon.com/stats/{month}/{fmt}-{ladder}.txt"

# Sleep moves ban list (SV OU; explicit sleep moves banned)
SLEEP_MOVES = {
    "Dark Void", "Grass Whistle", "Hypnosis", "Lovely Kiss", "Sing", "Sleep Powder", "Spore", "Yawn"
}

# Evasion Items clause
EVASION_ITEMS = {"Bright Powder", "Lax Incense"}

def fetch_usage_text(month: str, fmt: str, ladder: str) -> Tuple[str, str]:
    """Download a Smogon usage file and return (url, text). Raises for HTTP errors."""
    url = USAGE_BASE.format(month=month, fmt=fmt, ladder=ladder)
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return url, r.text

def parse_usage_file(text: str) -> Dict[str, Dict[str, float]]:
    """
    Parse the plain-text usage file.
    Returns: { species_name: {"usage": float, "rank": int} }
    """
    usage: Dict[str, Dict[str, float]] = {}
    line_re = re.compile(r"\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([0-9.]+)%\s*\|")
    for line in text.splitlines():
        m = line_re.search(line)
        if m:
            rank = int(m.group(1))
            name = m.group(2).strip()
            pct = float(m.group(3))
            usage[name] = {"rank": rank, "usage": pct}
    return usage

def get_allowed_species_from_usage(usage: Dict[str, Dict[str, float]]) -> Set[str]:
    """Species listed in the usage file are considered allowed for the selected format/month."""
    return set(usage.keys())

def load_sv_clauses() -> Dict[str, str]:
    """Return simple text for clauses we enforce in app (display only)."""
    return {
        "Species Clause": "No duplicate dex numbers (one of each species/forme).",
        "Sleep Moves Clause": "Moves that induce sleep are banned in SV OU.",
        "Evasion Items Clause": "Bright Powder and Lax Incense are banned.",
    }

def banned_sleep_moves() -> Set[str]:
    return SLEEP_MOVES

def banned_evasion_items() -> Set[str]:
    return EVASION_ITEMS

def tera_allowed_for_format(fmt: str) -> bool:
    """SV formats generally allow Terastallization; true for gen9ou."""
    return fmt.lower() in {"gen9ou", "gen9doublesou", "gen9uu", "gen9ru", "gen9nu", "gen9pu", "gen9lc"}

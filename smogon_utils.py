# smogon_utils.py
import json
import re
import requests
from typing import Dict, List, Tuple, Set, Optional
from bs4 import BeautifulSoup

USAGE_BASE = "https://www.smogon.com/stats/{month}/{fmt}-{ladder}.txt"
CHAOS_JSON = "https://www.smogon.com/stats/{month}/chaos/{fmt}-{ladder}.json"
MOVESET_TXT = "https://www.smogon.com/stats/{month}/moveset/{fmt}-{ladder}.txt"
DEX_OU_URL = "https://www.smogon.com/dex/sv/pokemon/{slug}/ou/"

# Sleep moves ban list (SV OU)
SLEEP_MOVES = {
    "Dark Void", "Grass Whistle", "Hypnosis", "Lovely Kiss", "Sing", "Sleep Powder", "Spore", "Yawn"
}
# Evasion Items clause
EVASION_ITEMS = {"Bright Powder", "Lax Incense"}

# -----------------------
# Usage list (species + ranks)
# -----------------------
def fetch_usage_text(month: str, fmt: str, ladder: str) -> Tuple[str, str]:
    url = USAGE_BASE.format(month=month, fmt=fmt, ladder=ladder)
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return url, r.text

def parse_usage_file(text: str) -> Dict[str, Dict[str, float]]:
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
    return set(usage.keys())

# -----------------------
# Chaos / moveset stats (per-Pokémon structure)
# -----------------------
def fetch_moveset_chaos(month: str, fmt: str, ladder: str) -> Optional[Dict]:
    """Try to load the OU 'chaos' JSON (best source)."""
    url = CHAOS_JSON.format(month=month, fmt=fmt, ladder=ladder)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def fetch_moveset_fallback(month: str, fmt: str, ladder: str) -> Optional[Dict]:
    """
    Fallback to moveset TXT which is actually JSON per month/format nowadays.
    """
    url = MOVESET_TXT.format(month=month, fmt=fmt, ladder=ladder)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        txt = r.text.strip()
        # Many months store json in this .txt
        data = json.loads(txt)
        return data
    except Exception:
        return None

def load_moveset_db(month: str, fmt: str, ladder: str) -> Dict[str, Dict]:
    """
    Return a dict keyed by species with fields similar to chaos:
    {
      "<Mon>": {
        "Abilities": {"Ability": usageFloat, ...},
        "Items": {"Item": usageFloat, ...},
        "Spreads": {"Nature:HP/Atk/Def/SpA/SpD/Spe": usageFloat, ...},
        "Moves": {"Move": usageFloat, ...},
        "Tera Types": {"Type": usageFloat, ...}  # sometimes missing
        "Teammates": {"Mon": usageFloat, ...},
        "Checks and Counters": {"Mon": [probWin, samples], ...} or list
      }
    }
    """
    chaos = fetch_moveset_chaos(month, fmt, ladder)
    if chaos and "data" in chaos:
        return chaos["data"]
    fallback = fetch_moveset_fallback(month, fmt, ladder)
    if fallback and "data" in fallback:
        return fallback["data"]
    return {}

def _sorted_top(d: Dict[str, float], limit: int) -> List[Tuple[str, float]]:
    return sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:limit]

def normalize_moveset_entry(entry: Dict, top_n_moves: int = 12) -> Dict:
    """Pick the top-N fields we care about for prompts/building."""
    if not entry:
        return {}
    abilities = _sorted_top(entry.get("Abilities", {}), 3)
    items = _sorted_top(entry.get("Items", {}), 4)
    spreads = _sorted_top(entry.get("Spreads", {}), 4)
    moves = _sorted_top(entry.get("Moves", {}), top_n_moves)
    tera = _sorted_top(entry.get("Tera Types", {}), 4) if "Tera Types" in entry else []
    teammates = _sorted_top(entry.get("Teammates", {}), 12)
    checks_raw = entry.get("Checks and Counters", {})
    # checks may be dict or list; normalize to list of (name, score)
    checks: List[Tuple[str, float]] = []
    if isinstance(checks_raw, dict):
        for k, v in checks_raw.items():
            try:
                if isinstance(v, list) and v:
                    checks.append((k, float(v[0])))
                elif isinstance(v, (int, float)):
                    checks.append((k, float(v)))
            except Exception:
                pass
    elif isinstance(checks_raw, list):
        for it in checks_raw:
            if isinstance(it, list) and len(it) >= 2:
                checks.append((str(it[0]), float(it[1])))
    checks = sorted(checks, key=lambda kv: kv[1], reverse=True)[:12]
    return {
        "abilities": abilities,
        "items": items,
        "spreads": spreads,
        "moves": moves,
        "tera": tera,
        "teammates": teammates,
        "checks": checks,
    }

def parse_spread_key(key: str) -> Tuple[str, Dict[str, int]]:
    """
    Key looks like 'Jolly:0/252/0/0/4/252' (HP/Atk/Def/SpA/SpD/Spe).
    Return (nature, EV dict).
    """
    try:
        nature, nums = key.split(":")
        parts = [int(x) for x in nums.split("/")]
        stats = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]
        evs = {s: parts[i] if i < len(parts) else 0 for i, s in enumerate(stats)}
        return nature, evs
    except Exception:
        return "Jolly", {"HP": 0, "Atk": 252, "Def": 0, "SpA": 0, "SpD": 4, "Spe": 252}

# -----------------------
# Strategy Dex scraping (best-effort)
# -----------------------
def slugify(mon: str) -> str:
    s = mon.lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]", "", s)
    return s

def fetch_dex_ou_summary(mon: str) -> Optional[str]:
    """
    Best-effort: fetch the OU dex page and extract some helpful text (first sections).
    If page is client-rendered, we still try to grab visible paragraphs.
    """
    url = DEX_OU_URL.format(slug=slugify(mon))
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        # Grab main content paragraphs near the 'Strategy' area
        # Heuristic: find all <p> under the root content
        paras = soup.find_all("p")
        text_bits: List[str] = []
        for p in paras[:12]:
            t = p.get_text(" ", strip=True)
            if len(t) > 40:
                text_bits.append(t)
        if text_bits:
            # Keep it short; the planner gets many mons
            return " ".join(text_bits)[:1200]
        return None
    except Exception:
        return None

# -----------------------
# Clauses / policies
# -----------------------
def load_sv_clauses() -> Dict[str, str]:
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
    return fmt.lower() in {"gen9ou", "gen9doublesou", "gen9uu", "gen9ru", "gen9nu", "gen9pu", "gen9lc"}

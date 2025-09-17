# teamgen.py
import json
import re
from dataclasses import dataclass
from typing import List, Dict, Tuple, Set, Optional

# If you want to use top spreads from stats when the plan omits them:
# You'll pass parse_spread_key in via smogon_utils (streamlit_app already has that context).
try:
    from smogon_utils import parse_spread_key  # optional import; only used if available
except Exception:
    def parse_spread_key(key: str):
        # Fallback parser: "Jolly:0/252/0/0/4/252"
        try:
            nature, nums = key.split(":")
            parts = [int(x) for x in nums.split("/")]
            stats = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]
            evs = {s: parts[i] if i < len(parts) else 0 for i, s in enumerate(stats)}
            return nature, evs
        except Exception:
            return "Jolly", {"HP": 0, "Atk": 252, "Def": 0, "SpA": 0, "SpD": 4, "Spe": 252}


# =========================
# Data structures
# =========================

@dataclass
class PokeSet:
    name: str
    item: str
    ability: str
    tera: Optional[str]
    evs: Dict[str, int]
    nature: str
    ivs: Optional[Dict[str, int]]
    moves: List[str]


STAT_ORDER = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]


# =========================
# LLM wrapper
# =========================

def call_llm_for_team(client, system_prompt: str, user_message: str, temperature: float = 0.6) -> str:
    """Light wrapper for Responses API."""
    resp = client.responses.create(
        model="gpt-4o-mini",
        temperature=temperature,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return resp.output_text


# =========================
# Planner: builds a strict JSON plan
# =========================

def build_planner_prompt(
    fmt: str,
    month: str,
    ladder: str,
    user_prompt: str,
    cand_context: str,
    ev_target: int,
    tera_allowed: bool,
) -> Tuple[str, str]:
    """
    Returns (system, user) prompts to produce a strict JSON plan with exactly six mons.
    """
    sys = f"""
You are a veteran Smogon team builder for SV {fmt.upper()} ({month}, ladder {ladder}).
Plan a serious, synergistic **six-Pokémon** team for Pokémon Showdown.

Hard rules for the JSON you output:
- Output **pure JSON** (no codefence). Top-level object with key "team" = list of six mon objects.
- Each mon MUST have EXACTLY these keys (and no extra):
  ["species","role","item","ability","nature","evs","tera","moves","rationale"]
  where:
    - "species": string (Smogon species name)
    - "role": short string (e.g., "hazard setter", "bulky pivot", "wincon")
    - "item": legal item string
    - "ability": legal ability string
    - "nature": legal nature string
    - "evs": object with keys {STAT_ORDER} (integers, multiples of 4, each ≤ 252, SUM = {ev_target})
    - "tera": null if Tera is not allowed; else a single type string (e.g., "Water") or null if not needed
    - "moves": array of **exactly 4** legal moves
    - "rationale": 1–3 sentences on why this set fits the team
- Avoid sleep-inducing moves; avoid evasion items.

Use Strategy Dex OU guidance with **~95% weight**; use OU stats context to break ties.
Ensure the six mons collectively cover: hazards and/or removal, speed control, breakers, pivoting, and solid defensive glue.
"""
    usr = f"""
User prompt:
{user_prompt}

Curated candidate context (per mon): Strategy Dex OU summary first (most important), then OU stats (items, abilities,
spreads/natures, moves, tera, teammates, checks). Prefer Dex guidance; use stats only to disambiguate.

{cand_context}
"""
    return sys, usr


def extract_plan_json(text: str) -> Dict:
    """Robustly parse the planner's JSON (strip codefences if present)."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("` \n")
        t = re.sub(r"^\w+\n", "", t)  # remove language hint
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"\{[\s\S]*\}\s*$", t)
        if m:
            return json.loads(m.group(0))
        raise


# =========================
# From plan → PokeSet list
# =========================

def _sanitize_move(m: str) -> str:
    return m.replace("-", " ").strip().title()


def sets_from_plan(
    plan: Dict,
    moveset_db: Optional[Dict[str, Dict]],
    tera_allowed: bool,
) -> List[PokeSet]:
    """
    Convert the planner's JSON into PokeSet objects.
    If nature/EVs/moves missing, fill from moveset_db top stats where possible.
    moveset_db format expected: { species: {"abilities":[(name,pct),...], "items":[...], "spreads":[(key,pct),...],
                                          "moves":[(name,pct),...], "tera":[(type,pct),...] } }
    """
    out: List[PokeSet] = []
    team = plan.get("team", []) if isinstance(plan, dict) else []
    for slot in team[:6]:
        species = str(slot.get("species", "")).strip()
        item = str(slot.get("item", "Leftovers")).strip() or "Leftovers"
        ability = str(slot.get("ability", "")).strip()
        nature = str(slot.get("nature", "")).strip()
        tera = slot.get("tera", None) if tera_allowed else None
        evs_in = slot.get("evs", {}) or {}
        evs = {s: int(evs_in.get(s, 0)) for s in STAT_ORDER}
        moves_list = slot.get("moves", []) or []
        moves = [_sanitize_move(m) for m in moves_list][:4]

        # Fill missing using stats if available
        ms = moveset_db.get(species, {}) if moveset_db else {}

        if (not nature) or (sum(evs.values()) == 0):
            spreads = ms.get("spreads", [])
            if spreads:
                nat0, ev0 = parse_spread_key(spreads[0][0])  # top spread
                if not nature:
                    nature = nat0
                if sum(evs.values()) == 0:
                    evs = ev0

        if not ability and ms.get("abilities"):
            ability = ms["abilities"][0][0]
        if (not item or item == "—") and ms.get("items"):
            item = ms["items"][0][0]
        if tera_allowed and (not tera) and ms.get("tera"):
            tera = ms["tera"][0][0]

        out.append(PokeSet(
            name=species or "Garchomp",
            item=item or "Leftovers",
            ability=ability or "Rough Skin",
            tera=tera,
            evs=evs,
            nature=nature or "Jolly",
            ivs=None,
            moves=moves if len(moves) == 4 else [],
        ))
    # If planner returned less than 6, pad with a generic mon to keep pipeline stable
    while len(out) < 6:
        out.append(PokeSet(
            name="Garchomp",
            item="Leftovers",
            ability="Rough Skin",
            tera=("Dragon" if tera_allowed else None),
            evs={"HP": 0, "Atk": 252, "Def": 0, "SpA": 0, "SpD": 4, "Spe": 252},
            nature="Jolly",
            ivs=None,
            moves=["Earthquake", "Stealth Rock", "Dragon Claw", "Protect"],
        ))
    return out[:6]


# =========================
# Export parsing (if you ever feed back through)
# =========================

SET_SPLIT_RE = re.compile(r"\n\s*\n+")
NAME_ITEM_RE = re.compile(r"^([^@\n]+?)\s*@\s*(.+)$")
ABILITY_RE = re.compile(r"^Ability:\s*(.+)$", re.I)
TERA_RE = re.compile(r"^Tera Type:\s*(.+)$", re.I)
EVS_RE = re.compile(r"^EVs:\s*(.+)$", re.I)
NATURE_RE = re.compile(r"^(\w+)\s+Nature$", re.I)
IVS_RE = re.compile(r"^IVs:\s*(.+)$", re.I)

def extract_sets(raw: str) -> List[str]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`\n ")
        raw = re.sub(r"^\w+\n", "", raw)
    return [p.strip() for p in SET_SPLIT_RE.split(raw) if p.strip()][:6]


def _parse_evs(evs_line: str) -> Dict[str, int]:
    pieces = [p.strip() for p in evs_line.split("/")]
    evs: Dict[str, int] = {s: 0 for s in STAT_ORDER}
    for p in pieces:
        m = re.match(r"(\d+)\s*(HP|Atk|Def|SpA|SpD|Spe)", p)
        if m:
            evs[m.group(2)] = int(m.group(1))
    return evs


def _parse_ivs(ivs_line: str) -> Dict[str, int]:
    pieces = [p.strip() for p in ivs_line.split("/")]
    ivs: Dict[str, int] = {}
    for p in pieces:
        m = re.match(r"(\d+)\s*(HP|Atk|Def|SpA|SpD|Spe)", p)
        if m:
            ivs[m.group(2)] = int(m.group(1))
    if not ivs:
        m2 = re.match(r"(\d+)\s*(HP|Atk|Def|SpA|SpD|Spe)", ivs_line.strip())
        if m2:
            ivs[m2.group(2)] = int(m2.group(1))
    return ivs


# =========================
# EV legality & helpers
# =========================

def _snap_target(total: int) -> int:
    total = max(0, min(510, total))
    return total - (total % 4)

def _ev_fixup(evs: Dict[str, int], target: int) -> Dict[str, int]:
    """
    Make EVs legal & aim for target:
    - target snapped to multiple of 4 within 0..510
    - per-stat clamp 0..252
    - all multiples of 4
    - redistribute in steps of 4 w/out infinite loops
    """
    target = _snap_target(target)
    adj = {}
    for s in STAT_ORDER:
        v = int(evs.get(s, 0))
        v = max(0, min(252, v))
        v -= (v % 4)
        adj[s] = v
    total = sum(adj.values())

    # Seed an offensive default if empty and target > 0
    if total == 0 and target > 0:
        adj = {s: 0 for s in STAT_ORDER}
        adj["Atk"] = 252
        adj["Spe"] = 252
        adj["SpD"] = 4
        total = sum(adj.values())

    incr_order = ["HP", "SpD", "Spe", "Def", "SpA", "Atk"]
    decr_order = ["HP", "SpD", "Spe", "Def", "SpA", "Atk"]

    # Reduce
    steps = 0
    while total > target and steps < 300:
        moved = False
        for s in decr_order:
            if total == target:
                break
            if adj[s] >= 4:
                adj[s] -= 4
                total -= 4
                moved = True
        if not moved:
            break
        steps += 1

    # Increase
    steps = 0
    while total < target and steps < 300:
        moved = False
        for s in incr_order:
            if total == target:
                break
            if adj[s] <= 248:
                adj[s] += 4
                total += 4
                moved = True
        if not moved:
            break
        steps += 1

    # Final clean
    for s in STAT_ORDER:
        adj[s] = max(0, min(252, adj[s] - (adj[s] % 4)))
    return adj


def _sanitize_item(item: str) -> str:
    return (item or "").strip() or "Leftovers"


def _legalize_item(item: str, ban_items: Set[str]) -> str:
    item = _sanitize_item(item)
    return "Leftovers" if item in ban_items else item


# =========================
# Final legality/normalization + export
# =========================

def normalize_and_validate_sets(
    sets: List[PokeSet],
    allowed_species: Set[str],
    usage: Dict[str, Dict[str, float]],
    ev_target: int,
    enforce_species_clause: bool,
    ban_sleep_moves: Set[str],
    ban_items: Set[str],
    tera_allowed: bool,
    moveset_db: Optional[Dict[str, Dict]] = None,
) -> Tuple[List[PokeSet], str]:
    """
    - Replace illegal species with high-usage legal ones
    - Fix EVs to target (multiples of 4, ≤252 each)
    - Guarantee exactly 4 moves; top up from stats if needed
    - Remove banned sleep moves; avoid evasion items
    - Enforce Species Clause
    """
    report_lines: List[str] = []
    parsed: List[PokeSet] = []

    ev_target_snapped = _snap_target(ev_target)
    if ev_target_snapped != ev_target:
        report_lines.append(f"[EV] Requested total {ev_target} is not a multiple of 4; using {ev_target_snapped}.")
    ev_target = ev_target_snapped

    for i, ps in enumerate(sets):
        # Species legality
        if ps.name not in allowed_species:
            legal_sorted = sorted(usage.items(), key=lambda kv: kv[1]['rank'])
            replacement = legal_sorted[min(i, len(legal_sorted)-1)][0]
            report_lines.append(f"[{i+1}] Replaced illegal species '{ps.name}' → '{replacement}'.")
            ps.name = replacement

        # EVs & nature
        ps.evs = _ev_fixup(ps.evs or {}, ev_target)
        ps.nature = ps.nature or "Jolly"

        # Item legality
        ps.item = _legalize_item(ps.item, ban_items)

        # Moves: sanitize, drop banned, top up to 4 from stats
        moves_in = ps.moves or []
        cleaned: List[str] = []
        for mv in moves_in:
            mm = _sanitize_move(mv)
            if mm and mm not in ban_sleep_moves:
                cleaned.append(mm)

        if len(cleaned) < 4:
            # top up from stats if available
            top_moves = []
            if moveset_db and moveset_db.get(ps.name) and moveset_db[ps.name].get("moves"):
                top_moves = moveset_db[ps.name]["moves"]  # list of (name, pct)
            for mv, _pct in top_moves:
                mm = _sanitize_move(mv)
                if mm not in cleaned and mm not in ban_sleep_moves:
                    cleaned.append(mm)
                if len(cleaned) == 4:
                    break
        # Absolute fallbacks
        fallbacks = ["Protect", "U-turn", "Knock Off", "Earthquake", "Shadow Ball", "Moonblast", "Flamethrower", "Surf"]
        while len(cleaned) < 4:
            for mm in fallbacks:
                if mm not in cleaned and mm not in ban_sleep_moves:
                    cleaned.append(mm)
                    break

        ps.moves = cleaned[:4]

        # Tera policy
        if not tera_allowed:
            ps.tera = None

        parsed.append(ps)

    # Species Clause (no duplicates)
    if enforce_species_clause:
        seen: Set[str] = set()
        for i, ps in enumerate(parsed):
            if ps.name in seen:
                for cand, _meta in sorted(usage.items(), key=lambda kv: kv[1]['rank']):
                    if cand not in seen:
                        report_lines.append(f"[{i+1}] Species Clause: replaced duplicate '{ps.name}' → '{cand}'.")
                        ps.name = cand
                        break
            seen.add(ps.name)

    return parsed, "\n".join(report_lines) if report_lines else "All checks passed."


def format_sets_export(sets: List[PokeSet], allow_tera: bool) -> str:
    out_blocks: List[str] = []
    for ps in sets:
        lines = [f"{ps.name} @ {ps.item}", f"Ability: {ps.ability or '—'}"]
        if allow_tera and ps.tera:
            lines.append(f"Tera Type: {ps.tera}")
        ev_parts = [f"{ps.evs.get(s,0)} {s}" for s in STAT_ORDER if ps.evs.get(s,0) > 0]
        if ev_parts:
            lines.append("EVs: " + " / ".join(ev_parts))
        lines.append(f"{ps.nature or 'Jolly'} Nature")
        if ps.ivs:
            iv_parts = [f"{ps.ivs.get(s)} {s}" for s in STAT_ORDER if ps.ivs.get(s) is not None]
            if iv_parts:
                lines.append("IVs: " + " / ".join(iv_parts))
        # Exactly 4 moves
        for mv in (ps.moves or [])[:4]:
            lines.append(mv)
        out_blocks.append("\n".join(lines))
    return "\n\n".join(out_blocks)

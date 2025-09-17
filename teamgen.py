# teamgen.py
import re
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass

# ----------------------
# Team & set helpers
# ----------------------

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


def build_prompt(fmt: str, month: str, ladder: str, user_prompt: str, usage: Dict[str, Dict[str, float]],
                 allowed_species: Set[str], tera_allowed: bool, ev_target: int) -> Tuple[str, str]:
    # Compress usage into a short list to bias choices
    top_species = sorted(usage.items(), key=lambda kv: kv[1]["rank"])[:50]
    top_names = ", ".join([n for n,_ in top_species])

    system = f"""
You are a Pokémon team building assistant for Smogon Showdown. Output must be EXACTLY Showdown export text for SIX sets, no commentary, no numbering, 1 blank line between sets. Format is {fmt} (SV), month {month} (ladder {ladder}).

Rules:
- Use ONLY Pokémon legal in {fmt} for {month}; prefer among: {top_names}.
- {'Include' if tera_allowed else 'Do NOT include'} a `Tera Type:` line.
- Each set must include: Name @ Item, Ability, {"Tera Type," if tera_allowed else ''} EVs, Nature, optional IVs, then exactly 4 legal moves.
- EVs must be multiples of 4 and total **exactly {ev_target}**. Common patterns: 252 / 252 / 4 or 244 / 252 / 12, etc.
- Obey SV clauses: no sleep-inducing moves; avoid evasion items.
- Species Clause: do not repeat species across the 6.
- Prefer meta-viable items/abilities/moves.
- Honor the user’s request.
"""

    user = user_prompt if user_prompt else "Generate a well-synergized balanced OU team with hazards, hazard control, a speed control option, and good defensive cores."
    return system, user


# ----------------------
# OpenAI call
# ----------------------

def call_llm_for_team(client, system_prompt: str, user_message: str, temperature: float = 0.7) -> str:
    resp = client.responses.create(
        model="gpt-4o-mini",
        temperature=temperature,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    # Extract text
    return resp.output_text


# ----------------------
# Parsing & validation
# ----------------------

SET_SPLIT_RE = re.compile(r"\n\s*\n+")
NAME_ITEM_RE = re.compile(r"^([^@\n]+?)\s*@\s*(.+)$")
ABILITY_RE = re.compile(r"^Ability:\s*(.+)$", re.I)
TERA_RE = re.compile(r"^Tera Type:\s*(.+)$", re.I)
EVS_RE = re.compile(r"^EVs:\s*(.+)$", re.I)
NATURE_RE = re.compile(r"^(\w+)\s+Nature$", re.I)
IVS_RE = re.compile(r"^IVs:\s*(.+)$", re.I)


def extract_sets(raw: str) -> List[str]:
    # Some models wrap in backticks; strip code fences
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`\n ")
        # Remove possible language hint
        raw = re.sub(r"^\w+\n", "", raw)
    parts = [p.strip() for p in SET_SPLIT_RE.split(raw) if p.strip()]
    # If model gave >6, take first 6
    return parts[:6]


def _parse_evs(evs_line: str) -> Dict[str, int]:
    # Format like: "252 Atk / 4 SpD / 252 Spe" or any subset of stats
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
    # Common shorthand: "IVs: 0 Atk"
    if not ivs:
        m2 = re.match(r"(\d+)\s*(HP|Atk|Def|SpA|SpD|Spe)", ivs_line.strip())
        if m2:
            ivs[m2.group(2)] = int(m2.group(1))
    return ivs


def _sum_evs(evs: Dict[str, int]) -> int:
    return sum(evs.values())


def _ev_fixup(evs: Dict[str, int], target: int) -> Dict[str, int]:
    # Make all multiples of 4 and sum to target by shaving/adding from HP first, then SpD, Spe
    adj = {k: v - (v % 4) for k, v in evs.items()}
    total = _sum_evs(adj)
    # If total is zero, provide a default spread 252/252/4 in Atk/Spe/SpD
    if total == 0:
        adj = {s: 0 for s in STAT_ORDER}
        adj["Atk"] = 252
        adj["Spe"] = 252
        adj["SpD"] = 4
        total = 508
    # Bring to target
    diff = target - total
    order = ["HP", "SpD", "Spe", "Def", "SpA", "Atk"]
    while diff != 0:
        for stat in order:
            if diff == 0:
                break
            if diff > 0:
                adj[stat] += 4
                diff -= 4
            else:
                if adj[stat] >= 4:
                    adj[stat] -= 4
                    diff += 4
    return adj


def _choose_replacement_move(species: str, usage: Dict[str, Dict[str, float]]) -> str:
    # Fallback generic moves; a real implementation could scrape detailed movesets per mon.
    common = [
        "Protect", "U-turn", "Volt Switch", "Knock Off", "Earthquake", "Ice Spinner", "Thunderbolt", "Flamethrower",
        "Surf", "Moonblast", "Shadow Ball", "Dragon Claw", "Play Rough", "Close Combat", "Extreme Speed", "Toxic Spikes",
    ]
    return common[0]


def _legalize_item(item: str, ban_items: Set[str]) -> str:
    if item in ban_items:
        return "Leftovers"
    return item


def parse_set(block: str, allow_tera: bool) -> PokeSet:
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    name, item = None, None
    ability, tera = None, None
    evs, ivs, moves = {}, None, []
    nature = None

    for ln in lines:
        if name is None:
            m = NAME_ITEM_RE.match(ln)
            if m:
                name, item = m.group(1).strip(), m.group(2).strip()
                continue
        m = ABILITY_RE.match(ln)
        if m: ability = m.group(1).strip(); continue
        m = TERA_RE.match(ln)
        if m: tera = m.group(1).strip(); continue
        m = EVS_RE.match(ln)
        if m: evs = _parse_evs(m.group(1)); continue
        m = NATURE_RE.match(ln)
        if m: nature = m.group(1).strip(); continue
        m = IVS_RE.match(ln)
        if m: ivs = _parse_ivs(m.group(1)); continue
        # Otherwise a move line
        if ln and not any(x in ln for x in ["@", "Ability:", "EVs:", "IVs:", "Nature", "Tera Type:"]):
            mv = ln.replace("-", " ").strip().title()
            moves.append(mv)

    return PokeSet(
        name=name or "Garchomp",
        item=item or "Leftovers",
        ability=ability or "Rough Skin",
        tera=(tera if allow_tera else None),
        evs=evs or {"HP": 0, "Atk": 252, "Def": 0, "SpA": 0, "SpD": 4, "Spe": 252},
        nature=nature or "Jolly",
        ivs=ivs,
        moves=moves[:4] if moves else ["Earthquake", "Stealth Rock", "Dragon Claw", "Protect"],
    )


def normalize_and_validate_sets(
    sets: List[str],
    allowed_species: Set[str],
    usage: Dict[str, Dict[str, float]],
    ev_target: int,
    enforce_species_clause: bool,
    ban_sleep_moves: Set[str],
    ban_items: Set[str],
    tera_allowed: bool,
) -> Tuple[List[PokeSet], str]:
    report_lines: List[str] = []
    parsed: List[PokeSet] = []

    for i, block in enumerate(sets):
        ps = parse_set(block, allow_tera=tera_allowed)

        # Species legality
        if ps.name not in allowed_species:
            # Replace with closest high-usage legal mon
            legal_sorted = sorted(usage.items(), key=lambda kv: kv[1]['rank'])
            replacement = legal_sorted[min(i, len(legal_sorted)-1)][0]
            report_lines.append(f"[{i+1}] Replaced illegal species '{ps.name}' → '{replacement}'.")
            ps.name = replacement

        # EV fixup
        ps.evs = _ev_fixup(ps.evs, ev_target)

        # Item legality
        ps.item = _legalize_item(ps.item, ban_items)

        # Move legality (sleep moves)
        fixed_moves = []
        for mv in ps.moves[:4]:
            if mv in ban_sleep_moves:
                repl = _choose_replacement_move(ps.name, usage)
                report_lines.append(f"[{i+1}] Replaced banned move '{mv}' → '{repl}'.")
                fixed_moves.append(repl)
            else:
                fixed_moves.append(mv)
        while len(fixed_moves) < 4:
            fixed_moves.append(_choose_replacement_move(ps.name, usage))
        ps.moves = fixed_moves[:4]

        # Tera line removal if not allowed
        if not tera_allowed:
            ps.tera = None

        parsed.append(ps)

    # Species Clause (no duplicates)
    if enforce_species_clause:
        seen: Set[str] = set()
        for i, ps in enumerate(parsed):
            if ps.name in seen:
                # pick next legal unused mon
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
        lines = [f"{ps.name} @ {ps.item}", f"Ability: {ps.ability}"]
        if allow_tera and ps.tera:
            lines.append(f"Tera Type: {ps.tera}")
        ev_parts = [f"{ps.evs.get(s,0)} {s}" for s in STAT_ORDER if ps.evs.get(s,0) > 0]
        if ev_parts:
            lines.append("EVs: " + " / ".join(ev_parts))
        lines.append(f"{ps.nature} Nature")
        if ps.ivs:
            iv_parts = [f"{ps.ivs.get(s)} {s}" for s in STAT_ORDER if ps.ivs.get(s) is not None]
            if iv_parts:
                lines.append("IVs: " + " / ".join(iv_parts))
        lines.extend(ps.moves[:4])
        out_blocks.append("\n".join(lines))
    return "\n\n".join(out_blocks)

# server/main.py  (FastAPI backend that matches the planner → JSON → sets flow)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import os
from typing import Dict, List, Tuple

from smogon_utils import (
    fetch_usage_text,
    parse_usage_file,
    get_allowed_species_from_usage,
    banned_sleep_moves,
    banned_evasion_items,
    tera_allowed_for_format,
    load_moveset_db,
    normalize_moveset_entry,
    fetch_dex_ou_summary,
    parse_spread_key,
)
from teamgen import (
    build_planner_prompt,
    call_llm_for_team,
    extract_plan_json,
    sets_from_plan,
    normalize_and_validate_sets,
    format_sets_export,
)

app = FastAPI()

class GenerateReq(BaseModel):
    fmt: str = "gen9ou"
    month: str = "2025-07"
    ladder: str = "1695"
    prompt: str
    ev_target: int = 508
    allow_tera: bool = True
    temperature: float = 0.35
    api_key: str | None = None
    top_k: int = 32  # number of candidate mons to include in context

def _build_candidate_context(
    usage: Dict[str, Dict[str, float]],
    moveset_db_raw: Dict[str, Dict],
    user_prompt: str,
    top_k: int = 32,
) -> str:
    """
    Same idea as the Streamlit app: compact per-mon blocks to guide the planner.
    """
    mentioned: List[str] = []
    up = (user_prompt or "").lower()
    for mon in usage.keys():
        if mon.lower() in up:
            mentioned.append(mon)

    top_list = [name for name, _ in sorted(usage.items(), key=lambda kv: kv[1]['rank'])[:top_k]]
    cands: List[str] = []
    for m in mentioned + top_list:
        if m not in cands:
            cands.append(m)

    blocks: List[str] = []
    for mon in cands[:top_k+len(mentioned)]:
        dex_summary = fetch_dex_ou_summary(mon) or ""
        ms = normalize_moveset_entry(moveset_db_raw.get(mon, {}), top_n_moves=12)

        items = ", ".join([f"{k}" for k,_ in (ms.get("items") or [])[:3]]) or "-"
        abilities = ", ".join([f"{k}" for k,_ in (ms.get("abilities") or [])[:2]]) or "-"
        nats = []
        for sp,_ in (ms.get("spreads") or [])[:2]:
            nat, _ = parse_spread_key(sp)
            nats.append(nat)
        natures = ", ".join(dict.fromkeys(nats)) or "-"
        moves = ", ".join([k for k,_ in (ms.get("moves") or [])[:8]]) or "-"
        tera = ", ".join([k for k,_ in (ms.get("tera") or [])[:3]]) or "-"
        mates = ", ".join([k for k,_ in (ms.get("teammates") or [])[:8]]) or "-"
        checks = ", ".join([k for k,_ in (ms.get("checks") or [])[:8]]) or "-"

        block = (
            f"=== {mon} ===\n"
            f"[DEX OU SUMMARY]\n{dex_summary}\n"
            f"[STATS] Items: {items} | Abilities: {abilities} | Natures: {natures} | "
            f"Moves: {moves} | Tera: {tera}\n"
            f"Teammates: {mates}\n"
            f"Checks/Counters: {checks}\n"
        )
        blocks.append(block)
    return "\n".join(blocks)

@app.post("/generate")
async def generate(req: GenerateReq):
    key = req.api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise HTTPException(400, "Missing API key")
    client = OpenAI(api_key=key)

    # Usage + allowed species
    _, text = fetch_usage_text(req.month, req.fmt, req.ladder)
    usage = parse_usage_file(text)
    allowed = get_allowed_species_from_usage(usage)

    # Moveset DB raw (for stats fill-ins)
    moveset_db_raw = load_moveset_db(req.month, req.fmt, req.ladder)
    moveset_db: Dict[str, Dict] = {}
    for mon, entry in moveset_db_raw.items():
        moveset_db[mon] = normalize_moveset_entry(entry, top_n_moves=20)

    # Candidate context (Dex + stats) → planner prompts
    cand_ctx = _build_candidate_context(usage, moveset_db_raw, req.prompt, top_k=req.top_k)
    sys_p, usr_p = build_planner_prompt(
        req.fmt, req.month, req.ladder, req.prompt, cand_ctx, req.ev_target, (tera_allowed_for_format(req.fmt) and req.allow_tera)
    )

    # LLM plan → JSON
    raw_plan = call_llm_for_team(client, sys_p, usr_p, temperature=req.temperature)
    plan = extract_plan_json(raw_plan)

    # Plan → sets (fill via stats if missing)
    sets = sets_from_plan(plan, moveset_db, tera_allowed=req.allow_tera)

    # Validate/normalize
    parsed, report = normalize_and_validate_sets(
        sets=sets,
        allowed_species=allowed,
        usage=usage,
        ev_target=req.ev_target,
        enforce_species_clause=True,
        ban_sleep_moves=banned_sleep_moves(),
        ban_items=banned_evasion_items(),
        tera_allowed=req.allow_tera,
        moveset_db=moveset_db,
    )
    export = format_sets_export(parsed, req.allow_tera)
    return {"export": export, "report": report}

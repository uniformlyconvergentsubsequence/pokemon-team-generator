# server/main.py  (optional FastAPI backend)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import os

from smogon_utils import (
    fetch_usage_text, parse_usage_file, get_allowed_species_from_usage,
    banned_sleep_moves, banned_evasion_items, tera_allowed_for_format
)
from teamgen import (
    build_prompt, call_llm_for_team, extract_sets,
    normalize_and_validate_sets, format_sets_export
)

app = FastAPI()

class GenerateReq(BaseModel):
    fmt: str = "gen9ou"
    month: str = "2025-07"
    ladder: str = "1695"
    prompt: str
    ev_target: int = 506
    allow_tera: bool = True
    temperature: float = 0.7
    api_key: str | None = None

@app.post("/generate")
async def generate(req: GenerateReq):
    key = req.api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise HTTPException(400, "Missing API key")
    client = OpenAI(api_key=key)

    _, text = fetch_usage_text(req.month, req.fmt, req.ladder)
    usage = parse_usage_file(text)
    allowed = get_allowed_species_from_usage(usage)

    sys_p, msg = build_prompt(
        req.fmt, req.month, req.ladder, req.prompt,
        usage, allowed,
        tera_allowed_for_format(req.fmt) and req.allow_tera,
        req.ev_target
    )
    raw = call_llm_for_team(client, sys_p, msg, req.temperature)
    sets = extract_sets(raw)
    parsed, report = normalize_and_validate_sets(
        sets, allowed, usage, req.ev_target, True,
        banned_sleep_moves(), banned_evasion_items(), req.allow_tera
    )
    export = format_sets_export(parsed, req.allow_tera)
    return {"export": export, "report": report}

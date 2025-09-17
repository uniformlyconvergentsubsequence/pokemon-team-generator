# streamlit_app.py
import os
from typing import List, Dict

import streamlit as st
from openai import OpenAI

from smogon_utils import (
    fetch_usage_text,
    parse_usage_file,
    get_allowed_species_from_usage,
    load_sv_clauses,
    banned_sleep_moves,
    banned_evasion_items,
    tera_allowed_for_format,
    load_moveset_db,
    normalize_moveset_entry,
    fetch_dex_ou_summary,
    parse_spread_key,   # <-- add this
)

from teamgen import (
    build_planner_prompt,
    call_llm_for_team,         # ← keep this here (top-level import)
    extract_plan_json,
    sets_from_plan,
    normalize_and_validate_sets,
    format_sets_export,
)


# -------------- helpers --------------
def build_candidate_context(
    usage: Dict[str, Dict[str, float]],
    moveset_db_raw: Dict[str, Dict],
    user_prompt: str,
    top_k: int = 32,
) -> str:
    """
    Construct a compact, per-mon context block:
    - Dex OU summary (first)
    - OU stats: top items, abilities, spreads (nature), moves, tera, teammates, checks
    """
    # prioritize mons mentioned in the user prompt
    mentioned: List[str] = []
    up = user_prompt.lower()
    for mon in usage.keys():
        if mon.lower() in up:
            mentioned.append(mon)

    top_list = [name for name, _ in sorted(usage.items(), key=lambda kv: kv[1]['rank'])[:top_k]]
    # De-dup with mentioned first
    cands: List[str] = []
    for m in mentioned + top_list:
        if m not in cands:
            cands.append(m)

    blocks: List[str] = []
    for mon in cands[:top_k+len(mentioned)]:
        dex_summary = fetch_dex_ou_summary(mon) or ""
        ms = normalize_moveset_entry(moveset_db_raw.get(mon, {}), top_n_moves=12)

        # Trim to keep prompt size reasonable
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

# -------------- app --------------
def main():
    st.set_page_config(page_title="Smogon Team Generator (SV OU)", layout="wide")
    st.title("Smogon Team Pokémon Generator — SV OU (Dex-guided)")

    with st.sidebar:
        st.header("API & Format")
        api_key = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))

        fmt = st.selectbox("Format", options=["gen9ou"], index=0)
        month = st.text_input("Stats month (YYYY-MM)", value="2025-07")
        ladder = st.selectbox("Ladder cutoff", options=["1695", "1825", "1500", "0"], index=0)

        st.header("Validation")
        ev_target = st.selectbox("EV total target", options=[508, 506, 510], index=0)  # default 508
        enforce_species_clause = st.checkbox("Enforce Species Clause (unique mons)", value=True)
        allow_tera = st.checkbox("Allow Tera (per-format)", value=True)

        st.header("Planner")
        top_k = st.slider("Candidate pool size from usage", 12, 48, 32, 4)
        temperature_plan = st.slider("Planner temperature", 0.0, 1.0, 0.35, 0.05)
        st.caption("Planner follows Strategy Dex (~95% weight) and uses OU stats to break ties.")

        st.header("Report")
        want_report = st.checkbox("Generate RMT-style report (I–VI)", value=True)

    st.write("Describe the team or constraints (playstyle, cores, must-include Pokémon, hazard plan, threats to answer, etc.).")
    user_prompt = st.text_area(
        "Prompt",
        height=140,
        placeholder="Example: Psyspam Trick Room built around Indeedee + Hatterene; must check Kingambit & Kyurem; include hazard control; one pivot."
    )

    if st.button("Generate Team", type="primary"):
        if not api_key:
            st.error("Please paste your OpenAI API key in the sidebar.")
            st.stop()

        client = OpenAI(api_key=api_key)

        # 1) Usage + allowed species
        with st.status("Loading OU usage…", expanded=False) as status:
            url, txt = fetch_usage_text(month, fmt, ladder)
            usage = parse_usage_file(txt)
            allowed_species = get_allowed_species_from_usage(usage)
            status.update(label=f"Loaded usage file: {url}", state="complete")

        # 2) Moveset DB (chaos/moveset)
        with st.status("Loading OU moveset data…", expanded=False):
            moveset_db_raw = load_moveset_db(month, fmt, ladder)
        # Pre-normalize for quick per-mon lookups later
        moveset_db: Dict[str, Dict] = {}
        for mon, entry in moveset_db_raw.items():
            moveset_db[mon] = normalize_moveset_entry(entry, top_n_moves=20)

        # 3) Candidate context (Dex summary + stats)
        with st.status("Compiling candidate context…", expanded=False):
            cand_ctx = build_candidate_context(usage, moveset_db_raw, user_prompt, top_k=top_k)

        # 4) Planner → JSON team
        sys_p, usr_p = build_planner_prompt(fmt, month, ladder, user_prompt, cand_ctx, ev_target, allow_tera)
        with st.status("Planning a synergistic team (Dex-guided)…", expanded=False):
            plan_text = call_llm_for_team(client, sys_p, usr_p, temperature=temperature_plan)
            plan = extract_plan_json(plan_text)

        # 5) Convert plan → PokeSets (fill with stats when missing)
        with st.status("Converting plan to sets…", expanded=False):
            sets = sets_from_plan(plan, moveset_db, tera_allowed=allow_tera)

        # 6) Validate & repair for legality, EVs, 4 moves, etc.
        clauses = load_sv_clauses()
        sleep_ban = banned_sleep_moves()
        evasion_items = banned_evasion_items()
        with st.status("Validating & fixing legality…", expanded=False):
            sets_valid, legality_report = normalize_and_validate_sets(
                sets=sets,
                allowed_species=allowed_species,
                usage=usage,
                ev_target=ev_target,
                enforce_species_clause=enforce_species_clause,
                ban_sleep_moves=sleep_ban,
                ban_items=evasion_items,
                tera_allowed=allow_tera,
                moveset_db=moveset_db,
            )

        export = format_sets_export(sets_valid, allow_tera)

        # UI
        tab_export, tab_legality = st.tabs(["Team Export", "Legality Report"])

        with tab_export:
            st.subheader("Showdown Export")
            st.code(export, language="text")
            st.download_button("Download team.txt", export.encode("utf-8"), file_name=f"{fmt}-{month}-team.txt", mime="text/plain")

        with tab_legality:
            st.subheader("Legality Report")
            st.write(legality_report)

        # 7) Optional RMT writeup
        if want_report:
            st.divider()
            st.subheader("Team Report (Smogon RMT style)")
            meta20 = ", ".join([name for name, _ in sorted(usage.items(), key=lambda kv: kv[1]['rank'])[:20]])
            sys_r = f"""
You are a Smogon RMT ghostwriter. Produce a Markdown RMT with sections:
I. Introduction
II. Building Process
III. Team Breakdown
IV. Threats/Usage Tips
V. Replays/Proof of Peak (placeholders)
VI. Outro

Ground yourself in the export (authoritative), the user's prompt, and the OU context listed. Explain synergies, roles, tera choices, and usage tips. Reference threats by name and our answers.

- Format: {fmt} (SV) — Month {month}, ladder {ladder}
- Meta top 20: {meta20}
- Terastallization: {"allowed" if allow_tera else "banned"}
- EV rule: total {ev_target}, 4-point increments; ≤252 per stat.
- Team export:
---
{export}
---
"""
            usr_r = f"""
User prompt:
{user_prompt}

If helpful, you may reference typical partners/counters (from OU stats knowledge), but do not repeat the full export again—just analysis.
"""
            report_md = call_llm_for_team(client, sys_r, usr_r, temperature=0.65)
            st.markdown(report_md)
            st.download_button("Download report.md", report_md.encode("utf-8"), file_name=f"{fmt}-{month}-report.md", mime="text/markdown")


if __name__ == "__main__":
    main()

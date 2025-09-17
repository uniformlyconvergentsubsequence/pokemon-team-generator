# streamlit_app.py
import os
import re
from typing import List, Dict, Optional

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
)
from teamgen import (
    build_prompt,
    call_llm_for_team,
    extract_sets,
    normalize_and_validate_sets,
    format_sets_export,
)

# ========= Helpers for the RMT report =========

def _top_meta_list(usage: Dict[str, Dict[str, float]], n: int = 20) -> List[str]:
    return [name for name, _ in sorted(usage.items(), key=lambda kv: kv[1]['rank'])[:n]]

def _slug_for_sprite(name: str) -> str:
    # Convert species name to Smogon sprite shortcode slug like :sv/iron_hands:
    slug = name.lower()
    slug = (slug
            .replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
            .replace(' ', '_'))
    # keep hyphens for formes like hoopa-unbound, landorus-therian
    slug = re.sub(r"[^a-z0-9_-]", "", slug)
    return slug

def _sprite_line_from_export(export_text: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", export_text) if b.strip()]
    mons: List[str] = []
    for b in blocks:
        first = b.splitlines()[0]
        species = first.split('@')[0].strip()
        mons.append(f":sv/{_slug_for_sprite(species)}:")
    return " ".join(mons)

def _build_report_prompt(
    fmt: str,
    month: str,
    ladder: str,
    user_prompt: str,
    usage: Dict[str, Dict[str, float]],
    export_text: str,
    style: str,
    tera_allowed: bool,
    ev_target: int,
    title: Optional[str] = None,
    sprite_line: Optional[str] = None,
    author: Optional[str] = None,
) -> tuple[str, str]:
    meta20 = ", ".join(_top_meta_list(usage, 20))

    header_bits = []
    if sprite_line:
        header_bits.append(sprite_line)
    if title:
        header_bits.append(title.upper())
    header = "\n".join(header_bits)

    system = f"""
You are a Smogon RMT ghostwriter. Write competitive, helpful analysis for Showdown players. Output must be **Markdown**, no HTML, and follow the requested structure exactly. Keep it clean and readable.
- Format: {fmt} (SV) — Month {month}, ladder {ladder}
- Assume Terastallization is {"allowed" if tera_allowed else "banned"}.
- EV policy: spreads sum to {ev_target} by app rule (multiples of 4).
- Meta reference (top 20 by usage): {meta20}
- Team export (authoritative):
---
{export_text}
---
- If a header is provided below, print it *before* section I.
HEADER_START
{header}
HEADER_END
"""

    if style.startswith("Smogon RMT"):
        user = (
            (f"Author credit: By {author}.\n" if author else "") +
            "Create a Smogon forum RMT-style writeup with these sections and headings exactly:"
            "\nI. Introduction"
            "\nII. Building Process"
            "\nIII. Team Breakdown"
            "\nIV. Threats/Usage Tips"
            "\nV. Replays/Proof of Peak (leave placeholder bullets)"
            "\nVI. Outro"
            "\n\nGuidelines:"
            "\n- Derive rationale from the team export and the user prompt. Explain synergies, roles, tera choices, items, and EV logic."
            "\n- In Team Breakdown, include a sub-section per Pokémon: role, move explanations, item/EV/nature notes, and quick tips."
            "\n- In Threats/Usage Tips, add a bullet list titled 'Answering the Meta' with 8–12 high-usage threats and how this team handles them."
            "\n- Use Smogon-esque tone; allow sprite shortcodes like :sv/gholdengo: when referencing Pokémon inline."
            "\n- Do NOT reprint the full team export; refer to it as 'the export above'."
        )
    else:
        user = (
            (f"Author credit: By {author}.\n" if author else "") +
            "Write concise scouting notes: a one-paragraph overview, then bullets for each Pokémon (role, key lines),"
            " and a final 'Versus common threats' list mapping top meta threats to our answers."
        )

    return system, user

def _call_llm_for_report(client, system_prompt: str, user_message: str, temperature: float = 0.85) -> str:
    resp = client.responses.create(
        model="gpt-4o-mini",
        temperature=temperature,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return resp.output_text

# ========= App =========

def main():
    st.set_page_config(page_title="Smogon Team Generator (SV OU)", layout="wide")
    st.title("Smogon Team Pokémon Generator — SV OU")

    with st.sidebar:
        st.header("Settings")
        api_key = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))

        st.caption("Format & Stats")
        fmt = st.selectbox("Format", options=["gen9ou"], index=0)
        month = st.text_input("Stats month (YYYY-MM)", value="2025-07")
        ladder = st.selectbox("Ladder cutoff", options=["1695", "1825", "1500", "0"], index=0)

        st.caption("Validation")
        ev_target = st.selectbox("EV total target", options=[506, 508, 510], index=0)
        enforce_species_clause = st.checkbox("Enforce Species Clause (unique mons)", value=True)
        allow_tera = st.checkbox("Allow Tera (per-format)", value=True)

        st.caption("LLM Settings")
        temperature = st.slider("Creativity (temperature)", 0.0, 1.4, 0.7, 0.1)

        st.divider()
        st.caption("Report Generation")
        want_report = st.checkbox("Generate detailed team report (RMT-style)", value=True)
        report_style = st.selectbox("Report style", ["Smogon RMT (I–VI)", "Concise scouting notes"], index=0)
        title = st.text_input("Report title (optional)")
        author = st.text_input("Author (optional)")
        include_sprites = st.checkbox("Include sprite shortcode header (:sv/mon:)", value=True)

    st.write("Enter what you want (playstyle, must-include Pokémon, cores, hazards, etc.).")
    user_prompt = st.text_area(
        "Prompt",
        height=120,
        placeholder="Example: Psyspam Trick Room with Indeedee + Hatterene; check Kingambit and Kyurem; include one pivot."
    )

    if st.button("Generate Team", type="primary"):
        if not api_key:
            st.error("Please paste your OpenAI API key in the sidebar.")
            st.stop()

        client = OpenAI(api_key=api_key)

        # 1) Smogon usage
        with st.status("Fetching Smogon usage…", expanded=False) as status:
            url, text = fetch_usage_text(month, fmt, ladder)
            status.update(label=f"Loaded usage: {url}", state="complete")

        usage = parse_usage_file(text)
        allowed_species = get_allowed_species_from_usage(usage)

        # 2) Clauses & policy
        _ = load_sv_clauses()  # informational
        sleep_ban = banned_sleep_moves()
        evasion_items = banned_evasion_items()

        # 3) Tera policy
        tera_allowed = allow_tera and tera_allowed_for_format(fmt)

        # 4) LLM → team
        sys_prompt, msg = build_prompt(
            fmt=fmt,
            month=month,
            ladder=ladder,
            user_prompt=user_prompt.strip(),
            usage=usage,
            allowed_species=allowed_species,
            tera_allowed=tera_allowed,
            ev_target=ev_target,
        )

        with st.status("Generating with OpenAI…", expanded=False):
            raw = call_llm_for_team(client, system_prompt=sys_prompt, user_message=msg, temperature=temperature)

        # 5) Validate
        with st.status("Validating & fixing legality…", expanded=False):
            sets = extract_sets(raw)
            sets_valid, legality_report = normalize_and_validate_sets(
                sets=sets,
                allowed_species=allowed_species,
                usage=usage,
                ev_target=ev_target,
                enforce_species_clause=enforce_species_clause,
                ban_sleep_moves=sleep_ban,
                ban_items=evasion_items,
                tera_allowed=tera_allowed,
            )

        export = format_sets_export(sets_valid, tera_allowed)

        # Tabs
        tab_export, tab_report, tab_legality = st.tabs(["Team Export", "Team Report", "Legality Report"])

        with tab_export:
            st.subheader("Showdown Export")
            st.code(export, language="text")
            st.download_button("Download team.txt", export.encode("utf-8"), file_name=f"{fmt}-{month}-team.txt", mime="text/plain")

        # 6) Report
        report_md = None
        if want_report:
            with st.status("Writing team report…", expanded=False):
                sprite_line = _sprite_line_from_export(export) if include_sprites else None
                sys_rpt, msg_rpt = _build_report_prompt(
                    fmt=fmt,
                    month=month,
                    ladder=ladder,
                    user_prompt=user_prompt.strip(),
                    usage=usage,
                    export_text=export,
                    style=report_style,
                    tera_allowed=tera_allowed,
                    ev_target=ev_target,
                    title=title or None,
                    sprite_line=sprite_line,
                    author=author or None,
                )
                report_md = _call_llm_for_report(
                    client,
                    system_prompt=sys_rpt,
                    user_message=msg_rpt,
                    temperature=min(temperature + 0.15, 1.2),
                )

        with tab_report:
            if want_report and report_md:
                st.markdown(report_md)
                st.download_button(
                    "Download report.md",
                    report_md.encode("utf-8"),
                    file_name=f"{fmt}-{month}-report.md",
                    mime="text/markdown",
                )
            else:
                st.info(
                    "Enable \"Generate detailed team report\" in the sidebar to get a Smogon-style writeup with "
                    "rationale, building process, threat answers, and usage tips."
                )

        with tab_legality:
            st.subheader("Legality Report")
            st.write(legality_report)


if __name__ == "__main__":
    main()

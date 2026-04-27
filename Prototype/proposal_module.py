"""
proposal_module.py
==================
DesignVoyager - Proposal Module

Uses OpenAI to propose a new game mechanic as Python code, with a small
repair loop when the generated code is malformed.
"""

import ast
import json
import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(PROJECT_DIR, ".env"))

API_KEY = os.getenv("OPENAI_API_KEY", "PLEASE_SET_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL", None)
MODEL = "gpt-5.4-nano"
MAX_REPAIR_ATTEMPTS = 3

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

_SYSTEM_PROMPT_TEMPLATE = """You are an expert game designer working with a Python game framework.
{state_description}

Your job is to propose a new game mechanic as a Python function with this exact signature:

    def mechanic_name(game_state: dict) -> dict:
        return game_state

The function must:
1. Accept and return the game_state dict
2. Only use Python standard library plus numpy imported as np
3. Be safe, with no infinite loops, file I/O, or network calls
4. Meaningfully change the game, not a no-op

Always respond in this exact JSON format, raw JSON only:
{{
    "mechanic_name": "snake_case_name",
    "mechanic_type": "one of: scoring | movement | resource | exception | termination | other",
    "description": "One clear sentence describing what this mechanic does",
    "justification": "One sentence explaining why this improves the game",
    "python_code": "import numpy as np\\n\\ndef mechanic_name(game_state: dict) -> dict:\\n    return game_state"
}}"""

_DEFAULT_STATE_DESCRIPTION = (
    "The game uses a state dictionary with these keys:\n"
    "  - 'board'          : a 2D numpy array of single characters ('_' = blank, 'X' = player 1, 'O' = player 2)\n"
    "  - 'current_player' : integer (1 or 2)\n"
    "  - 'turn'           : integer turn count"
)


def _build_system_prompt(state_description: str = None) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(
        state_description=state_description or _DEFAULT_STATE_DESCRIPTION
    )


def build_proposal_prompt(game_skeleton: str, retrieved_mechanics: list,
                          stage_prompt: str = "", user_prompt: str = "",
                          banned_names: list = None, is_revision: bool = False) -> str:
    mechanics_section = ""
    if retrieved_mechanics:
        mechanics_section = "\n\nHere are some previously validated mechanics for reference:\n"
        for i, mech in enumerate(retrieved_mechanics, 1):
            mechanics_section += (
                f"\n--- Mechanic {i}: {mech.get('mechanic_name', 'Unknown')} ---\n"
                f"Type: {mech.get('mechanic_type', '')}\n"
                f"Description: {mech.get('description', '')}\n"
                f"Code:\n{mech.get('python_code', '')}\n"
            )

    library_names = [
        m.get("mechanic_name", "")
        for m in retrieved_mechanics
        if not m.get("mechanic_name", "").endswith("(PREVIOUS ATTEMPT - FAILED)")
    ]
    all_banned = sorted(set(library_names) | set(banned_names or []))
    dedup_section = ""
    if all_banned and not is_revision:
        names_str = ", ".join(all_banned)
        dedup_section = (
            "\n\nDo NOT propose a mechanic with any of these names "
            f"(already used or previously discarded): {names_str}. "
            "Your mechanic must have a unique name and be functionally distinct "
            "from everything listed above."
        )

    stage_section = f"\n\n{stage_prompt}" if stage_prompt else ""
    user_section = f"\n\n{user_prompt}" if user_prompt else ""
    closing = (
        "Fix the mechanic shown above. Keep the same core idea but correct the issue "
        "described in the revision feedback. Respond with raw JSON only."
        if is_revision else
        "Propose ONE new mechanic that meaningfully extends this game. "
        "Respond with raw JSON only."
    )
    return (
        f"Current game:\n{game_skeleton}"
        f"{mechanics_section}"
        f"{dedup_section}"
        f"{stage_section}"
        f"{user_section}\n\n"
        f"{closing}"
    )


def build_repair_prompt(broken_code: str, error: str) -> str:
    return (
        f"The Python code has an error:\n\n```python\n{broken_code}\n```\n\n"
        f"Error: {error}\n\n"
        "Fix it and respond with the complete corrected JSON."
    )


def validate_python_syntax(code: str) -> tuple:
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError line {e.lineno}: {e.msg}"


def parse_gpt_response(text: str) -> Optional[dict]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  [Proposal] JSON parse error: {e}")
        return None


def propose_mechanic(game_skeleton: str, retrieved_mechanics: list = None,
                     stage_prompt: str = "", user_prompt: str = "",
                     state_description: str = None, banned_names: list = None,
                     is_revision: bool = False) -> Optional[dict]:
    if retrieved_mechanics is None:
        retrieved_mechanics = []

    print(f"\n[Proposal] Starting... ({len(retrieved_mechanics)} prior mechanics retrieved)")

    messages = [
        {"role": "system", "content": _build_system_prompt(state_description)},
        {
            "role": "user",
            "content": build_proposal_prompt(
                game_skeleton, retrieved_mechanics, stage_prompt, user_prompt,
                banned_names=banned_names, is_revision=is_revision
            ),
        },
    ]

    for attempt in range(1, MAX_REPAIR_ATTEMPTS + 1):
        print(f"[Proposal] Attempt {attempt}/{MAX_REPAIR_ATTEMPTS}...")
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.8,
                timeout=60.0,
            )
            response_text = response.choices[0].message.content
        except Exception as e:
            print(f"  [Proposal] API error: {e}")
            continue

        mechanic = parse_gpt_response(response_text)
        if mechanic is None:
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": "Invalid JSON. Respond ONLY with raw JSON."})
            continue

        code = mechanic.get("python_code", "")
        is_valid, error = validate_python_syntax(code)

        if is_valid:
            print(
                f"  [Proposal] accepted '{mechanic.get('mechanic_name')}'"
                f" | Type: {mechanic.get('mechanic_type')}"
            )
            return mechanic

        print(f"  [Proposal] Syntax error: {error}")
        if attempt < MAX_REPAIR_ATTEMPTS:
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": build_repair_prompt(code, error)})

    print("[Proposal] all attempts failed")
    return None

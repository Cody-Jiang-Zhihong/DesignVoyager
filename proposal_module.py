"""
proposal_module.py
==================
DesignVoyager — Proposal Module
Author: Morgan Waddington

What this file does (plain English):
    This is the "brain" that talks to GPT-4 and asks it to invent a new game mechanic.
    It takes the current game description and some examples of mechanics that already worked,
    sends them to GPT-4, and gets back a new mechanic written as Python code.
    If the code GPT-4 writes has a bug, it automatically tries to fix it (up to 3 times).
    If it still can't fix it after 3 tries, it gives up and returns None.

How it connects to the rest of the system:
    - INPUT  from: Mechanic Library (Ziyi's module) — provides retrieved_mechanics
    - INPUT  from: Game Skeleton   (shared) — the current state of the game
    - OUTPUT  to: Playtest Module  (Cody's module) — the proposed mechanic dict
"""

import os
import ast
import json
from typing import Optional
from openai import OpenAI


# -------------------------------------------------------
# CONFIGURATION — Set your API key here
# -------------------------------------------------------
#
# Option A — NYU Portkey (free for NYU students, recommended):
#   1. Ask your instructor for the Portkey base URL and API key
#   2. Set these two environment variables before running:
#        export OPENAI_API_KEY="your-portkey-api-key"
#        export OPENAI_BASE_URL="https://api.portkey.ai/v1"  (or whatever URL NYU gave you)
#
# Option B — Your personal OpenAI key ($4 account):
#   1. Set this environment variable:
#        export OPENAI_API_KEY="sk-..."
#   (Leave OPENAI_BASE_URL unset)
#
# On Windows, use "set" instead of "export", or just paste the key directly below.
#
API_KEY  = os.getenv("OPENAI_API_KEY", "PASTE_YOUR_KEY_HERE")
BASE_URL = os.getenv("OPENAI_BASE_URL", None)   # Leave None for standard OpenAI

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
MODEL  = "gpt-4"
MAX_REPAIR_ATTEMPTS = 3   # How many times to retry if GPT writes broken code


# -------------------------------------------------------
# PROMPT TEMPLATES
# -------------------------------------------------------

SYSTEM_PROMPT = """You are an expert game designer working with the Boardwalk framework,
a Python-based system for creating two-player board games. Your job is to propose new
game mechanics as Python functions that can be added to an existing game.

Each mechanic you propose must:
1. Be implemented as a self-contained Python function compatible with the Boardwalk API
2. Meaningfully extend the current game (not just a trivial variation)
3. Aim to improve playability, balance, or strategic depth

Always respond in this exact JSON format (no markdown, just raw JSON):
{
    "mechanic_name": "snake_case_name",
    "mechanic_type": "one of: scoring | movement | resource | exception | termination | other",
    "description": "One clear sentence describing what this mechanic does",
    "justification": "One or two sentences explaining why this improves the game",
    "python_code": "def mechanic_name(game_state, **kwargs):\\n    # full implementation\\n    pass"
}"""


def build_proposal_prompt(game_skeleton: str, retrieved_mechanics: list) -> str:
    """
    Build the prompt that asks GPT-4 to propose a new mechanic.

    Args:
        game_skeleton       : A text description (or code) of the current game
        retrieved_mechanics : Up to 3 previously validated mechanics from the library

    Returns:
        A formatted string ready to send to GPT-4
    """
    mechanics_section = ""
    if retrieved_mechanics:
        mechanics_section = "\n\nFor reference, here are some mechanics that have already been validated:\n"
        for i, mech in enumerate(retrieved_mechanics, 1):
            mechanics_section += (
                f"\n--- Mechanic {i}: {mech.get('mechanic_name', 'Unknown')} ---\n"
                f"Type: {mech.get('mechanic_type', 'unknown')}\n"
                f"Description: {mech.get('description', '')}\n"
                f"Code:\n{mech.get('python_code', '')}\n"
            )

    return (
        f"Current game skeleton:\n{game_skeleton}"
        f"{mechanics_section}\n\n"
        "Please propose ONE new game mechanic that meaningfully extends this game.\n"
        "Respond with raw JSON only — no markdown, no explanation outside the JSON."
    )


def build_repair_prompt(broken_code: str, error_message: str) -> str:
    """
    Build a prompt asking GPT-4 to fix code that had an error.

    Args:
        broken_code   : The Python code that failed
        error_message : The error that was produced when we tried to parse/run it

    Returns:
        A formatted repair prompt string
    """
    return (
        f"The Python code you provided has an error:\n\n"
        f"```python\n{broken_code}\n```\n\n"
        f"Error:\n{error_message}\n\n"
        "Please diagnose and fix the issue. "
        "Respond with the complete corrected JSON (same format as before)."
    )


# -------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------

def validate_python_syntax(code: str) -> tuple:
    """
    Check if a string of Python code is syntactically valid.

    Args:
        code: Python code as a string

    Returns:
        (is_valid: bool, error_message: str)
        If valid, error_message will be an empty string.
    """
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError on line {e.lineno}: {e.msg}"


def parse_gpt_response(response_text: str) -> Optional[dict]:
    """
    Parse GPT-4's text response into a Python dictionary.

    GPT sometimes wraps JSON in markdown code fences (```json ... ```)
    even when told not to. This function strips those out before parsing.

    Args:
        response_text: The raw text string returned by GPT-4

    Returns:
        A Python dict if parsing succeeded, or None if it failed.
    """
    text = response_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove opening fence (```json or ```) and closing fence (```)
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  [ProposalModule] JSON parse error: {e}")
        return None


# -------------------------------------------------------
# MAIN FUNCTION
# -------------------------------------------------------

def propose_mechanic(game_skeleton: str, retrieved_mechanics: list = None) -> Optional[dict]:
    """
    Ask GPT-4 to propose a new game mechanic, with automatic repair on failure.

    This is the main function the rest of the system will call.

    Args:
        game_skeleton       : Text description or code of the current game state
        retrieved_mechanics : List of up to 3 mechanic dicts from the library (can be empty)

    Returns:
        A dictionary with these keys on success:
            - mechanic_name  (str)
            - mechanic_type  (str)
            - description    (str)
            - justification  (str)
            - python_code    (str)
        Returns None if all repair attempts were exhausted.
    """
    if retrieved_mechanics is None:
        retrieved_mechanics = []

    print(f"\n[ProposalModule] Starting mechanic proposal...")
    print(f"[ProposalModule] Retrieved {len(retrieved_mechanics)} mechanics from library.")

    # Build the first prompt
    initial_prompt = build_proposal_prompt(game_skeleton, retrieved_mechanics)

    # This is the conversation history we send to GPT-4
    messages = [
        {"role": "system",  "content": SYSTEM_PROMPT},
        {"role": "user",    "content": initial_prompt},
    ]

    for attempt in range(1, MAX_REPAIR_ATTEMPTS + 1):
        print(f"[ProposalModule] Attempt {attempt}/{MAX_REPAIR_ATTEMPTS}...")

        # --- Call GPT-4 ---
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.8,    # A bit of creativity, but not too unpredictable
            )
            response_text = response.choices[0].message.content
        except Exception as e:
            print(f"  [ProposalModule] API call failed: {e}")
            return None

        # --- Parse the JSON ---
        mechanic = parse_gpt_response(response_text)
        if mechanic is None:
            print("  [ProposalModule] Response was not valid JSON. Asking GPT to retry...")
            messages.append({"role": "assistant", "content": response_text})
            messages.append({
                "role": "user",
                "content": "Your response was not valid JSON. Please respond ONLY with the raw JSON object, no markdown."
            })
            continue

        # --- Validate the Python code ---
        code = mechanic.get("python_code", "")
        is_valid, error = validate_python_syntax(code)

        if is_valid:
            print(f"  [ProposalModule] ✓ Success! Mechanic: '{mechanic.get('mechanic_name')}'")
            return mechanic
        else:
            print(f"  [ProposalModule] Code has a syntax error: {error}")
            if attempt < MAX_REPAIR_ATTEMPTS:
                print("  [ProposalModule] Asking GPT to fix it...")
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": build_repair_prompt(code, error)})

    print(f"[ProposalModule] ✗ All {MAX_REPAIR_ATTEMPTS} attempts failed. Returning None.")
    return None


# -------------------------------------------------------
# QUICK TEST — run this file directly to try it out
# python proposal_module.py
# -------------------------------------------------------

if __name__ == "__main__":
    # A simple game description to test with
    test_skeleton = """
    Two-player board game on a 6x6 grid.
    Players take turns placing their colored pieces on empty squares.
    A player wins by getting 4 of their pieces in a row
    (horizontally, vertically, or diagonally).
    Current mechanics: basic placement only.
    """

    # Start with an empty library (no prior mechanics yet)
    test_mechanics = []

    result = propose_mechanic(test_skeleton, test_mechanics)

    if result:
        print("\n========== Proposed Mechanic ==========")
        print(f"Name        : {result['mechanic_name']}")
        print(f"Type        : {result['mechanic_type']}")
        print(f"Description : {result['description']}")
        print(f"Justification: {result['justification']}")
        print(f"\nPython Code:\n{result['python_code']}")
        print("=======================================")
    else:
        print("\nNo mechanic was successfully proposed.")

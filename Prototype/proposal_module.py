"""
proposal_module.py
==================
DesignVoyager - Proposal Module

Uses OpenAI to propose a new game mechanic as a Python function, with a
small repair loop if the returned code has syntax errors.
"""

import ast
import json
import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
MAX_REPAIR_ATTEMPTS = 3

# Game-specific mechanic type definitions
BOARD_GAME_MECHANIC_TYPES = {
    "movement": "After placing a piece, the player may perform an additional operation involving that newly placed piece or an empty space adjacent to it. This extra operation must have a clear gameplay purpose and must not be a trivial relocation of the piece to another square. The mechanic may be reusable across the game, but it must require a specific trigger or precondition rather than allowing unrestricted free actions.",
    "resource": "A one-time skill available to each player only once during the entire game. The skill may restrict the opponent, strengthen the acting player, or meaningfully change the board state.",
    "exception": "A triggered mechanic that activates automatically when a specific board condition is satisfied. It may interrupt or alter the normal game flow once its condition is met.",
    "termination": "An alternative game-ending mechanic that introduces additional win conditions beyond the base rules. It should be deliberately non-trivial in structure, designed with strong attention to balance, and must avoid creating an extreme first-player advantage.",
}

CARD_GAME_MECHANIC_TYPES = {
    "combo": "A mechanic in which the card played on the current turn can meaningfully interact with the card played on the previous turn. If the two-turn sequence satisfies a specific pattern or goal, the player gains an additional reward.",
    "exception": "A triggered mechanic that activates automatically when a specific game-state condition is satisfied. Once triggered, it may alter the normal flow of the card game or temporarily change how the current game proceeds.",
    "hand": "A mechanic that primarily changes which cards in one or both publicly visible hands can be used, kept, removed, exchanged, locked, or reinterpreted. Because the card game has no hidden information and no deck, the mechanic should focus on meaningful changes to playable hand state or card value interpretation, rather than card reveal, draw effects, or simple reordering that does not affect decision-making.",
    "resource": "A one-time skill available to each player only once during the entire game. The skill may restrict the opponent, strengthen the acting player, or meaningfully change the current card-state or scoring situation.",
    "tempo": "A mechanic that primarily changes turn flow or action timing in the card game. It may grant an extra turn, delay an effect, skip or alter an opponent's next action, or otherwise shift the pace and sequencing of play.",
}


def _build_client() -> OpenAI:
    kwargs = {}
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert game designer working with a Python game framework.
{state_description}

Your job is to propose a new game mechanic as a Python function with this exact signature:

    def mechanic_name(game_state: dict) -> dict:
        # modifies game_state and returns it
        return game_state

The function must:
1. Accept and return the game_state dict
2. Only use Python standard library + numpy (imported as np)
3. Be safe - no infinite loops, no file I/O, no network calls
4. Meaningfully change the game (not a no-op)

CRITICAL NAMING REQUIREMENT:
The mechanic_name MUST follow this EXACT format: "{{mechanic_type}}_{{descriptive_name}}"
- Start with one of the valid mechanic_type values listed below
- Followed by exactly one underscore
- Followed by a descriptive snake_case name (e.g., "movement_diagonal_shift", "combo_cascade", "tempo_double_turn")
Valid mechanic types and their definitions:
{mechanic_types}

Always respond in this exact JSON format (raw JSON only, no markdown):
{{
    "mechanic_name": "mechanic_type_descriptive_name",
    "mechanic_type": "one of the valid types listed above",
    "description": "One clear sentence describing what this mechanic does",
    "justification": "One sentence explaining why this improves the game",
    "python_code": "import numpy as np\\n\\ndef mechanic_name(game_state: dict) -> dict:\\n    # implementation\\n    return game_state"
}}"""

_BOARD_GAME_MECHANIC_TYPES_STR = "\n".join(
    f"- {name}: {desc}"
    for name, desc in BOARD_GAME_MECHANIC_TYPES.items()
)

_CARD_GAME_MECHANIC_TYPES_STR = "\n".join(
    f"- {name}: {desc}"
    for name, desc in CARD_GAME_MECHANIC_TYPES.items()
)

_DEFAULT_STATE_DESCRIPTION = (
    "The game uses a state dictionary with these keys:\n"
    "  - 'board'          : a 2D numpy array of single characters "
    "('_' = blank, 'X' = player 1, 'O' = player 2)\n"
    "  - 'current_player' : integer (1 or 2)\n"
    "  - 'turn'           : integer turn count\n"
    "  - 'last_move'      : tuple (row, col) of the most recent piece placement, "
    "or None on the very first call\n"
    "  - 'extra_turn'     : boolean, default False. Set to True to give the current "
    "player an extra turn.\n"
    "  - 'custom_state'   : dict, default {}. Use this to store any persistent "
    "mechanic state between turns.\n"
    "IMPORTANT: Only use the keys listed above. Do NOT assume any other keys exist."
)


def _build_system_prompt(state_description: str = None, game_type: str = "board") -> str:
    desc = state_description or _DEFAULT_STATE_DESCRIPTION
    mechanic_types_str = (
        _BOARD_GAME_MECHANIC_TYPES_STR if game_type == "board"
        else _CARD_GAME_MECHANIC_TYPES_STR if game_type == "card"
        else _BOARD_GAME_MECHANIC_TYPES_STR  # default to board
    )
    return _SYSTEM_PROMPT_TEMPLATE.format(
        state_description=desc,
        mechanic_types=mechanic_types_str
    )


SYSTEM_PROMPT = _build_system_prompt()


def build_proposal_prompt(
    game_skeleton: str,
    retrieved_mechanics: list,
    stage_prompt: str = "",
    banned_names: list = None,
    is_revision: bool = False,
) -> str:
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
        dedup_section = (
            "\n\nDo NOT propose a mechanic with any of these names "
            f"(already used or previously discarded): {', '.join(all_banned)}. "
            "Your mechanic must have a unique name and be functionally distinct."
        )

    stage_section = f"\n\n{stage_prompt}" if stage_prompt else ""
    closing = (
        "Fix the mechanic shown above. Keep the same core idea but correct the issue "
        "described in the revision feedback. Respond with raw JSON only."
        if is_revision
        else "Propose ONE new mechanic that meaningfully extends this game. Respond with raw JSON only."
    )

    return (
        f"Current game:\n{game_skeleton}"
        f"{mechanics_section}"
        f"{dedup_section}"
        f"{stage_section}\n\n"
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


def parse_response(text: str) -> Optional[dict]:
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


def propose_mechanic(
    game_skeleton: str,
    retrieved_mechanics: list = None,
    stage_prompt: str = "",
    state_description: str = None,
    banned_names: list = None,
    is_revision: bool = False,
    game_type: str = "board",
    stream_cb=None,
) -> Optional[dict]:
    if retrieved_mechanics is None:
        retrieved_mechanics = []

    print(f"\n[Proposal] Starting... ({len(retrieved_mechanics)} prior mechanics retrieved)")

    client = _build_client()
    system_prompt = _build_system_prompt(state_description, game_type=game_type)
    next_message = build_proposal_prompt(
        game_skeleton,
        retrieved_mechanics,
        stage_prompt=stage_prompt,
        banned_names=banned_names,
        is_revision=is_revision,
    )
    messages = [{"role": "system", "content": system_prompt}]

    for attempt in range(1, MAX_REPAIR_ATTEMPTS + 1):
        print(f"[Proposal] Attempt {attempt}/{MAX_REPAIR_ATTEMPTS}...")
        try:
            messages.append({"role": "user", "content": next_message})
            if stream_cb is not None:
                response_text = ""
                last_emit_len = 0
                with client.chat.completions.stream(
                    model=MODEL,
                    messages=messages,
                    temperature=1.0,
                    response_format={"type": "json_object"},
                ) as stream:
                    for event in stream:
                        if event.type != "content.delta":
                            continue
                        chunk_text = event.delta or ""
                        if not chunk_text:
                            continue
                        response_text += chunk_text
                        if len(response_text) - last_emit_len >= 24:
                            try:
                                stream_cb(response_text)
                            except Exception:
                                pass
                            last_emit_len = len(response_text)
                try:
                    stream_cb(response_text)
                except Exception:
                    pass
            else:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    temperature=1.0,
                    response_format={"type": "json_object"},
                )
                response_text = response.choices[0].message.content or ""
        except Exception as e:
            print(f"  [Proposal] API error: {e}")
            continue

        messages.append({"role": "assistant", "content": response_text})
        mechanic = parse_response(response_text)
        if mechanic is None:
            next_message = "Invalid JSON. Respond ONLY with raw JSON."
            continue

        code = mechanic.get("python_code", "")
        is_valid, error = validate_python_syntax(code)
        if is_valid:
            print(f"  [Proposal] OK '{mechanic.get('mechanic_name')}'")
            return mechanic

        print(f"  [Proposal] Syntax error: {error}")
        if attempt < MAX_REPAIR_ATTEMPTS:
            next_message = build_repair_prompt(code, error)

    print("[Proposal] All attempts failed.")
    return None

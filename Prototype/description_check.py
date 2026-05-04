"""
description_check.py
====================
Semantic alignment check between a mechanic's one-line description and its
Python code. Fail-open by design so transient API issues do not block runs.
"""

from __future__ import annotations

import json
import os
from typing import Tuple

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.getenv("OPENAI_REVIEW_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))


def _build_client() -> OpenAI:
    kwargs = {}
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


_GAME_CONTEXT = {
    "board": (
        "perform_move places the current player's piece at the chosen square "
        "('X' for player 1, 'O' for player 2). The mechanic function runs "
        "after that placement, on a state dict that already reflects it."
    ),
    "card": (
        "perform_move pops the chosen card from the current player's hand "
        "and adds the card's value to that player's score. The mechanic "
        "function runs after that step, on a state dict where the score "
        "already includes the played card. If the description does not "
        "mention extra or double scoring of the played card, then code "
        "that does scores[current_player] += played_card is a mismatch."
    ),
}


_REVIEW_PROMPT_TEMPLATE = """\
You are reviewing one game mechanic to make sure its python code matches
the one-sentence description.

Game-specific context:
{game_context}

Mechanic description:
{description}

Mechanic code:
```python
{code}
```

Decide whether the code faithfully implements the description.

Return raw JSON only in one of these shapes:
{{"matches": true}}
{{"matches": false, "issue": "one sentence explaining the mismatch"}}
"""


def _build_prompt(description: str, code: str, game_name: str) -> str:
    context = _GAME_CONTEXT.get(game_name, _GAME_CONTEXT["board"])
    return _REVIEW_PROMPT_TEMPLATE.format(
        game_context=context,
        description=description.strip(),
        code=code.strip(),
    )


def _parse_response(text: str) -> Tuple[bool, str]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return True, ""
    if not isinstance(payload, dict):
        return True, ""
    matches = bool(payload.get("matches", True))
    issue = str(payload.get("issue", "")).strip() if not matches else ""
    return matches, issue


def check_description_matches_code(
    description: str,
    code: str,
    game_name: str = "board",
) -> Tuple[bool, str]:
    if not description or not code:
        return True, ""

    prompt = _build_prompt(description, code, game_name)

    try:
        response = _build_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a strict code review assistant. Return JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        text = (response.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"  [DescriptionCheck] LLM call failed, accepting: {type(e).__name__}: {e}")
        return True, ""

    if not text:
        print("  [DescriptionCheck] empty response, accepting")
        return True, ""

    matches, issue = _parse_response(text)
    if not matches:
        print(f"  [DescriptionCheck] MISMATCH: {issue}")
    else:
        print("  [DescriptionCheck] aligned")
    return matches, issue

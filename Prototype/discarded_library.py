"""
discarded_library.py
====================
Persistent record of discarded mechanic names.

These names are loaded at the start of a run and passed into the proposal
module so the model avoids re-proposing known-bad ideas.
"""

import json
import os


def load(filepath: str) -> list:
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Discarded] Could not load {filepath}: {e}. Starting fresh.")
        return []


def save_name(name: str, filepath: str):
    if not name:
        return
    names = load(filepath)
    if name in names:
        return
    names.append(name)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(names, f, indent=2)
    print(f"[Discarded] Recorded '{name}' ({len(names)} total in {filepath})")


def clear(filepath: str):
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"[Discarded] Cleared {filepath}")
    else:
        print(f"[Discarded] Nothing to clear ({filepath} not found)")

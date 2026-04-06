"""
verification_module.py
======================
DesignVoyager - Self-Verification Module
"""

MIN_PLAYABILITY = 1.0
MAX_BALANCE_GAP = 0.45
MIN_AGGREGATE = 0.70

ACCEPT = "accept"
REVISE = "revise"
DISCARD = "discard"


def verify(mechanic: dict, scores: dict, already_revised: bool = False) -> tuple:
    name = mechanic.get("mechanic_name", "unknown")
    playability = scores.get("playability", 0)
    balance_gap = scores.get("balance_gap", 1)
    aggregate = scores.get("aggregate", 0)

    print(f"[Verify] Evaluating '{name}'...")

    if playability < MIN_PLAYABILITY:
        feedback = (
            f"The mechanic caused too many games to not finish properly "
            f"(playability={playability:.0%}, minimum is {MIN_PLAYABILITY:.0%}). "
            f"The mechanic may be causing infinite loops, crashes, or removing "
            f"all valid moves. Please simplify the logic or add a safety guard."
        )
        print(f"  [Verify] DISCARD - failed playability gate ({playability:.0%})")
        return DISCARD, feedback

    if balance_gap > MAX_BALANCE_GAP:
        feedback = (
            f"The mechanic creates a large first-player advantage "
            f"(balance_gap={balance_gap:.0%}, maximum is {MAX_BALANCE_GAP:.0%}). "
            f"Consider making the mechanic symmetric so it benefits both players equally."
        )
        if already_revised:
            print("  [Verify] DISCARD - extreme imbalance after revision")
            return DISCARD, feedback
        print("  [Verify] REVISE - extreme imbalance")
        return REVISE, feedback

    if aggregate < MIN_AGGREGATE:
        feedback = (
            f"The mechanic's overall score is too low (aggregate={aggregate:.2f}, "
            f"minimum is {MIN_AGGREGATE:.2f}). "
            f"Try proposing a more impactful mechanic that noticeably changes "
            f"strategy or rewards skilled play."
        )
        if already_revised:
            print("  [Verify] DISCARD - low aggregate score after revision")
            return DISCARD, feedback
        print("  [Verify] REVISE - low aggregate score")
        return REVISE, feedback

    print(f"  [Verify] ACCEPT - aggregate={aggregate:.2f}")
    return ACCEPT, "Mechanic accepted."

"""
demo_main.py
============
DesignVoyager - presentation-ready terminal runner.

Supports both board and card games. Board mode keeps the MCTS-based playtest.
"""

import argparse
import contextlib
import io
import os

from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from base_game import BaseGame
from card_game import CardGame
from compile_check import compile_check
from curriculum import Curriculum
from mechanic_library import MechanicLibrary
from playtest_module import playtest
from proposal_module import propose_mechanic
from verification_module import ACCEPT, DISCARD, REVISE, MIN_PLAYABILITY, verify
import discarded_library

load_dotenv()

console = Console()

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

GAME_REGISTRY = {
    "board": (
        BaseGame,
        os.path.join(PROJECT_DIR, "library.json"),
        os.path.join(PROJECT_DIR, "discarded_board.json"),
    ),
    "card": (
        CardGame,
        os.path.join(PROJECT_DIR, "library_card.json"),
        os.path.join(PROJECT_DIR, "discarded_card.json"),
    ),
}


@contextlib.contextmanager
def suppress():
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def score_bar(value: float, width: int = 26) -> str:
    filled = int(value * width)
    bar = "█" * filled + "░" * (width - filled)
    color = "green" if value >= 0.75 else ("yellow" if value >= 0.50 else "red")
    return f"[{color}]{bar}[/{color}]  [bold]{value:.2f}[/bold]"


def print_scores(scores: dict):
    balance = round(1 - scores["balance_gap"], 2)
    playability = scores.get("playability", 0)
    if playability >= MIN_PLAYABILITY:
        console.print("  [dim]Playability gate[/dim]  [bold green]passed[/bold green]")
    else:
        console.print(
            f"  [dim]Playability gate[/dim]  [bold red]failed[/bold red] "
            f"[dim]({playability:.0%} of games finished, need 100%)[/dim]"
        )
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column(style="dim", width=14, no_wrap=True)
    table.add_column(no_wrap=True)
    table.add_row("Balance", score_bar(balance))
    table.add_row("Depth", score_bar(scores["depth"]))
    table.add_row("-" * 12, "-" * 34)
    table.add_row("Aggregate", score_bar(scores["aggregate"]))
    console.print(table)


def print_verdict(decision: str, name: str, scores: dict = None):
    if decision == ACCEPT:
        agg = f"\n  [dim]aggregate score: [bold]{scores['aggregate']:.2f}[/bold][/dim]" if scores else ""
        console.print(Panel(f"  [bold green]{name}[/bold green]{agg}", title="ACCEPTED", border_style="bright_green"))
    elif decision == REVISE:
        console.print(Panel(f"  [yellow]{name}[/yellow]\n  [dim]Sending revision feedback...[/dim]", title="REVISING", border_style="yellow"))
    else:
        console.print(Panel(f"  [red]{name}[/red]\n  [dim]Could not produce a working mechanic.[/dim]", title="DISCARDED", border_style="red"))


def _compile_playtest_verify(mechanic: dict, already_revised: bool, game_class=None, dummy_state: dict = None) -> tuple:
    console.print("  [dim]Compile check[/dim]", end="  ")
    with suppress():
        ok, error = compile_check(mechanic, dummy_state=dummy_state)

    if not ok:
        console.print("[bold red]failed[/bold red]")
        console.print(f"  [red dim]{error[:90]}[/red dim]\n")
        if already_revised:
            return DISCARD, {}
        mechanic["_revision_feedback"] = f"The code crashed: {error}. Please rewrite to fix this."
        return REVISE, {}

    console.print("[bold green]passed[/bold green]")

    with console.status(f"  [cyan]Playtesting [bold]{mechanic['mechanic_name']}[/bold]...[/cyan]"):
        with suppress():
            scores = playtest(mechanic, game_class=game_class)

    print_scores(scores)

    with suppress():
        decision, feedback = verify(mechanic, scores, already_revised)
    if decision == REVISE:
        mechanic["_revision_feedback"] = feedback

    return decision, scores


def _check_novelty_gate(mechanic: dict, library: MechanicLibrary, already_revised: bool) -> str | None:
    similar_entry, similarity = library.find_most_similar(mechanic)
    if similar_entry is None:
        return None

    mechanic["_revision_feedback"] = (
        f"This mechanic is too similar to existing library mechanic "
        f"'{similar_entry['mechanic_name']}' (similarity {similarity:.3f}). "
        "Please propose a functionally distinct mechanic before playtesting."
    )
    return DISCARD if already_revised else REVISE


def run_loop(n_iterations: int = 3, top_k: int = 3, game_name: str = "board", user_prompt: str = ""):
    game_class, library_file, discarded_file = GAME_REGISTRY[game_name]
    game_template = game_class.create()
    skeleton = game_template.get_skeleton_description()
    state_desc = game_template.get_state_description()
    dummy_state = game_template.get_dummy_state()

    with suppress():
        library = MechanicLibrary(filepath=library_file)
    curriculum = Curriculum()
    banned_names = discarded_library.load(discarded_file)
    tried_this_run = set()

    console.print()
    console.print(Panel(
        f"[bold cyan]DesignVoyager[/bold cyan]\n\n"
        f"  Game  [bold white]{game_name}[/bold white]     "
        f"Iterations  [bold white]{n_iterations}[/bold white]     "
        f"Context k  [bold white]{top_k}[/bold white]\n"
        f"  Library  [bold cyan]{library.size()} mechanics[/bold cyan]\n"
        f"  Curriculum  [yellow]{curriculum.progress_str()}[/yellow]\n"
        f"  Banned  [dim]{len(banned_names)} previously discarded mechanics[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))

    accepted_count = 0
    discarded_count = 0

    for iteration in range(1, n_iterations + 1):
        console.print()
        console.rule(f"[bold white]Iteration {iteration} of {n_iterations}[/bold white] [dim]| {curriculum.stage_name()} | {game_name}[/dim]")
        console.print()

        retrieval_query = f"{skeleton} {curriculum.stage_name()} {user_prompt}".strip()
        with suppress():
            retrieved = library.retrieve(k=top_k, query=retrieval_query)

        if retrieved:
            names = ", ".join(m["mechanic_name"] for m in retrieved)
            console.print(f"  [dim]Context from library:[/dim] [cyan]{names}[/cyan]\n")
        else:
            console.print("  [dim]No library context yet.[/dim]\n")

        with console.status(f"  [cyan]Designing a new mechanic for {game_name}...[/cyan]"):
            with suppress():
                mechanic = propose_mechanic(
                    skeleton,
                    retrieved,
                    stage_prompt=curriculum.stage_prompt(),
                    user_prompt=user_prompt,
                    state_description=state_desc,
                    banned_names=list(set(banned_names) | tried_this_run),
                )

        if mechanic is None:
            print_verdict(DISCARD, "-")
            curriculum.on_discard()
            discarded_count += 1
            continue
        tried_this_run.add(mechanic.get("mechanic_name", ""))

        pre_playtest_revised = False
        similarity_outcome = _check_novelty_gate(mechanic, library, already_revised=False)
        if similarity_outcome == REVISE:
            print_verdict(REVISE, mechanic["mechanic_name"])
            console.print("  [dim]Novelty gate triggered before playtest; requesting a more distinct mechanic.[/dim]\n")
            feedback = mechanic.get("_revision_feedback", "Please propose a more distinct mechanic.")
            revision_ctx = retrieved + [{
                "mechanic_name": f"{mechanic['mechanic_name']} (PREVIOUS ATTEMPT - TOO SIMILAR)",
                "mechanic_type": mechanic.get("mechanic_type", "other"),
                "description": mechanic.get("description", ""),
                "python_code": mechanic.get("python_code", ""),
            }]
            revised_skeleton = (
                skeleton
                + f"\n\nNOVELTY GATE FEEDBACK for '{mechanic['mechanic_name']}':\n{feedback}\n"
                + "Please propose a more distinct mechanic before playtesting."
            )
            with console.status(f"  [yellow]Revising {mechanic['mechanic_name']} before playtest...[/yellow]"):
                with suppress():
                    revised = propose_mechanic(
                        revised_skeleton,
                        revision_ctx,
                        stage_prompt=curriculum.stage_prompt(),
                        user_prompt=user_prompt,
                        state_description=state_desc,
                        banned_names=list(set(banned_names) | tried_this_run),
                        is_revision=True,
                    )
            if revised is None:
                print_verdict(DISCARD, mechanic["mechanic_name"])
                discarded_library.save_name(mechanic.get("mechanic_name", ""), discarded_file)
                banned_names.append(mechanic.get("mechanic_name", ""))
                curriculum.on_discard()
                discarded_count += 1
                continue

            tried_this_run.add(revised.get("mechanic_name", ""))
            if _check_novelty_gate(revised, library, already_revised=True) == DISCARD:
                print_verdict(DISCARD, revised["mechanic_name"])
                console.print("  [dim red]Revised mechanic still duplicates the accepted library, so playtest was skipped.[/dim red]\n")
                discarded_library.save_name(revised.get("mechanic_name", ""), discarded_file)
                banned_names.append(revised.get("mechanic_name", ""))
                curriculum.on_discard()
                discarded_count += 1
                continue
            mechanic = revised
            pre_playtest_revised = True

        console.print(
            f"\n  [cyan bold]Proposed:[/cyan bold] [bold white]{mechanic['mechanic_name']}[/bold white] "
            f"[dim]({mechanic.get('mechanic_type', '')})[/dim]\n"
            f"  [dim]{mechanic.get('description', '')}[/dim]\n"
        )

        decision, scores = _compile_playtest_verify(
            mechanic,
            already_revised=pre_playtest_revised,
            game_class=game_class,
            dummy_state=dummy_state,
        )

        if decision == REVISE:
            print_verdict(REVISE, mechanic["mechanic_name"])
            console.print()
            feedback = mechanic.get("_revision_feedback", "Please improve this mechanic.")
            revision_ctx = retrieved + [{
                "mechanic_name": f"{mechanic['mechanic_name']} (PREVIOUS ATTEMPT - FAILED)",
                "mechanic_type": mechanic.get("mechanic_type", "other"),
                "description": mechanic.get("description", ""),
                "python_code": mechanic.get("python_code", ""),
            }]
            revised_skeleton = (
                skeleton
                + f"\n\nREVISION FEEDBACK for '{mechanic['mechanic_name']}':\n{feedback}\n"
                + "Please propose a corrected version that fixes the issue described above."
            )

            with console.status(f"  [yellow]Revising {mechanic['mechanic_name']}...[/yellow]"):
                with suppress():
                    revised = propose_mechanic(
                        revised_skeleton,
                        revision_ctx,
                        stage_prompt=curriculum.stage_prompt(),
                        user_prompt=user_prompt,
                        state_description=state_desc,
                        banned_names=list(set(banned_names) | tried_this_run),
                        is_revision=True,
                    )

            if revised is None:
                print_verdict(DISCARD, mechanic["mechanic_name"])
                discarded_library.save_name(mechanic.get("mechanic_name", ""), discarded_file)
                banned_names.append(mechanic.get("mechanic_name", ""))
                curriculum.on_discard()
                discarded_count += 1
                continue

            mechanic = revised
            tried_this_run.add(mechanic.get("mechanic_name", ""))
            console.print(f"\n  [yellow bold]Revised:[/yellow bold] [bold white]{mechanic['mechanic_name']}[/bold white]\n")
            decision, scores = _compile_playtest_verify(
                mechanic,
                already_revised=True,
                game_class=game_class,
                dummy_state=dummy_state,
            )

        console.print()
        print_verdict(decision, mechanic["mechanic_name"], scores if decision == ACCEPT else None)
        console.print()

        if decision == ACCEPT:
            with suppress():
                added = library.add(mechanic, scores, iteration=iteration)
            advanced = curriculum.on_accept()
            accepted_count += 1
            if not added:
                console.print(
                    "  [dim yellow]Accepted by verification, but not stored because it duplicates an existing library entry.[/dim yellow]"
                )
            if advanced:
                console.print(Panel(
                    f"  [bold yellow]Unlocked {curriculum.stage_name()}[/bold yellow]\n"
                    f"  [dim]The proposal module can now attempt more complex mechanics.[/dim]",
                    border_style="yellow",
                ))
        else:
            discarded_library.save_name(mechanic.get("mechanic_name", ""), discarded_file)
            banned_names.append(mechanic.get("mechanic_name", ""))
            curriculum.on_discard()
            discarded_count += 1

    summary = Table(title="\n  Run Complete", box=box.ROUNDED, border_style="cyan", padding=(0, 4), show_header=False)
    summary.add_column(style="dim", width=14)
    summary.add_column(justify="right")
    summary.add_row("Accepted", f"[bold green]{accepted_count}[/bold green]")
    summary.add_row("Discarded", f"[red]{discarded_count}[/red]")
    summary.add_row(
        "Library",
        f"[bold cyan]{library.size()} mechanics[/bold cyan]"
        if library.size() else "[dim]empty[/dim]",
    )
    console.print(summary)
    console.print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DesignVoyager - animated demo mode")
    parser.add_argument("--iterations", "-n", type=int, default=3)
    parser.add_argument("--top-k", "-k", type=int, default=3)
    parser.add_argument("--game", "-g", type=str, choices=list(GAME_REGISTRY.keys()), default="board")
    parser.add_argument("--user-prompt", "-u", type=str, default="")
    args = parser.parse_args()
    run_loop(n_iterations=args.iterations, top_k=args.top_k, game_name=args.game, user_prompt=args.user_prompt)

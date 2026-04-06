# DesignVoyager Prototype Session Handoff

## Current State

`Prototype/` is now the active merged prototype.

It includes:
- multi-game support via `game_interface.py`
- board game support via `base_game.py`
- card game support via `card_game.py`
- board-game MCTS playtesting
- card-game MCTS playtesting
- cross-platform subprocess-based timeouts for Windows and macOS
- runtime self-verification JSON reports written to `runtime_reports/`

## Main Entry Points

Run board mode:

```bash
python main.py --game board
```

Run card mode:

```bash
python main.py --game card
```

Demo mode:

```bash
python demo_main.py --game board
python demo_main.py --game card
```

## Important Notes

- `self_verification_sample.json` remains the schema reference.
- Real runtime reports are now emitted under `runtime_reports/`.
- `playtest_module.py` is the main integration point for MCTS, raw metrics, and runtime reporting.
- `main.py` writes one JSON report per candidate mechanic.

# Prototype

This is the active DesignVoyager prototype.

## What It Supports

- `board` game mode via `base_game.py`
- `card` game mode via `card_game.py`
- MCTS-based playtesting
- Cross-platform subprocess-based game execution for Windows and macOS
- Runtime self-verification reports

## Main Files

- `main.py`: main loop
- `demo_main.py`: presentation-friendly terminal runner
- `playtest_module.py`: automated playtesting, MCTS evaluation, runtime report generation
- `game_interface.py`: shared game contract
- `self_verification_sample.json`: schema example for self-verification integration
- `runtime_reports/`: generated JSON reports from actual runs
- `board_experiment_record_and_report.md`: sample board experiment write-up

## Running

Install dependencies:

```bash
python -m pip install -r Prototype/requirements.txt
```

Run board mode:

```bash
python Prototype/main.py --game board
```

Run card mode:

```bash
python Prototype/main.py --game card
```

Run demo mode:

```bash
python Prototype/demo_main.py --game board
python Prototype/demo_main.py --game card
```

## Experiment Outputs

Runtime reports are written to:

- `Prototype/runtime_reports/`

Each run produces a structured JSON file containing:

- mechanic metadata
- integration report
- parent metrics
- child metrics
- trigger stats
- derived scores

## Notes

- Board and card playtests both use MCTS.
- `self_verification_sample.json` is the schema reference.
- `board_experiment_record_and_report.md` is a repo-friendly exported experiment document.

# Prototype

This is the active DesignVoyager prototype.

## What It Supports

- `board` game mode via `base_game.py`
- `card` game mode via `card_game.py`
- MCTS-based playtesting
- Cross-platform subprocess-based game execution for Windows and macOS
- FastAPI dashboard with live pipeline logs, mechanic tutorials, replay, and library browsing
- Runtime self-verification reports
- Discarded-mechanic memory to reduce duplicate or previously failed proposals
- Accepted-only library registration with duplicate filtering

## Main Files

- `main.py`: main loop
- `demo_main.py`: presentation-friendly terminal runner
- `playtest_module.py`: automated playtesting, MCTS evaluation, runtime report generation
- `mechanic_library.py`: accepted mechanic library with semantic retrieval and duplicate filtering
- `discarded_library.py`: persistent memory of discarded mechanic names
- `game_interface.py`: shared game contract
- `web/app.py`: dashboard server
- `web/pipeline_runner.py`: dashboard pipeline adapter
- `self_verification_sample.json`: schema example for self-verification integration
- `runtime_reports/`: generated JSON reports from actual runs
- `board_experiment_record_and_report.md`: sample board experiment write-up
- `card_experiment_record_and_report.md`: sample card experiment write-up
- `latest_combined_experiment_report.md`: latest combined board/card experiment results
- `card_metric_review.md`: card playtest metric review and calibration notes

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

Run the web dashboard:

```bash
cd Prototype
python -m uvicorn web.app:app --reload --port 8000
```

Then open:

```text
http://localhost:8000
```

The dashboard now uses the same accepted libraries as the CLI:

- `Prototype/library.json` for board mechanics
- `Prototype/library_card.json` for card mechanics

`Prototype/library_cards.json` is only used to store dashboard replay/tutorial metadata.

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

Discarded mechanic names are stored separately as:

- `discarded_board.json`
- `discarded_card.json`

These files are used by the proposal module to avoid re-proposing known-bad
or already discarded mechanic names in later runs.

Accepted mechanic libraries are stored as:

- `library.json`
- `library_card.json`

Only mechanics that are both:

- accepted by verification
- not rejected by duplicate filtering

are actually registered into these libraries.

Latest experiment/reference documents:

- `board_experiment_record_and_report.md`
- `card_experiment_record_and_report.md`
- `latest_combined_experiment_report.md`
- `card_metric_review.md`

## Notes

- Board and card playtests both use MCTS.
- The proposal module avoids library duplicates and previously discarded names when possible.
- Card mode now uses symmetric initial hands and card-specific playtest budgets to reduce metric noise.
- Dashboard library cards are merged from accepted library entries plus optional replay metadata.
- `self_verification_sample.json` is the schema reference.
- `latest_combined_experiment_report.md` is the newest consolidated run summary.

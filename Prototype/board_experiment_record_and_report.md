# Board Experiment Record and Report

## Experiment Record

### Setup

- Game: `board`
- Evaluation budget:
  - Balance: 12 games of `MCTS(low) vs MCTS(low)`
  - Depth: 12 games of `MCTS(strong) vs MCTS(weak)`
- Stage: `Stage 1 - Simple`
- Context size: `top-k = 1`

### Runtime Reports Used

- [board_iter00_noop_mechanic_file_initial.json](runtime_reports/board_iter00_noop_mechanic_file_initial.json)
- [board_iter01_line_lock_on_placement_initial.json](runtime_reports/board_iter01_line_lock_on_placement_initial.json)
- [board_iter01_placement_with_splash_freeze_line_revised.json](runtime_reports/board_iter01_placement_with_splash_freeze_line_revised.json)
- [board_iter01_line_of_sight_block_on_placement_revised.json](runtime_reports/board_iter01_line_of_sight_block_on_placement_revised.json)

### Results Table

| Run | Prompt Intent | Final Mechanic | Playability | Balance Gap | Depth | Aggregate | P1 Win Rate | P2 Win Rate | Strong Win Rate | Weak Win Rate |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | No-op control | `noop_mechanic_file` | 1.000 | 0.000 | 0.667 | 0.834 | 0.500 | 0.500 | 0.833 | 0.167 |
| Run 1 | Symmetric mechanic | `line_lock_on_placement` | 1.000 | 0.333 | 1.000 | 0.834 | 0.667 | 0.333 | 1.000 | 0.000 |
| Run 2 | Biased prompt, revised | `placement_with_splash_freeze_line` | 1.000 | 0.000 | 0.667 | 0.834 | 0.500 | 0.500 | 0.833 | 0.167 |
| Run 3 | Strategic prompt, revised | `line_of_sight_block_on_placement` | 1.000 | 0.000 | 0.667 | 0.834 | 0.500 | 0.500 | 0.833 | 0.167 |

### Notes

- The biased-prompt run first proposed `adjacent_blocked_by_placement`, which scored `aggregate = 0.584` and triggered revision before the accepted revised mechanic.
- The strategic-prompt run first proposed `adjacent_block_on_placement`, which scored `aggregate = 0.667` and also triggered revision before the accepted revised mechanic.
- All four final recorded runs were fully playable.

## Experiment Report

This experiment evaluated the board-game version of DesignVoyager under a small but consistent MCTS-based protocol. Each final candidate mechanic was tested with 12 balance games using low-budget MCTS on both sides, and 12 depth games using strong-budget MCTS against weak-budget MCTS. The objective was to check whether the system could run simulated games reliably and whether the current balance and depth metrics produced interpretable differences.

The baseline no-op control produced perfect playability, zero balance gap, and moderate depth (`0.667`). Two accepted revised mechanics, `placement_with_splash_freeze_line` and `line_of_sight_block_on_placement`, matched the baseline on balance while preserving the same depth score and aggregate score. This suggests that the current evaluation pipeline can generate mechanics that remain fair without reducing strategic signal.

The most distinct result came from `line_lock_on_placement`. It remained fully playable and achieved the maximum observed depth score (`1.000`), indicating a strong advantage for the stronger MCTS agent. However, it also produced a noticeable balance gap (`0.333`), with player 1 winning twice as often as player 2. This makes it a useful example of a mechanic that appears strategically rich but may introduce fairness concerns.

Overall, the experiment shows that the board playtest pipeline is operational and capable of producing meaningful metrics for playability, balance, and strategic depth. The current setup is good enough for iterative development and for demonstrating Cody's contribution in slides or a progress report. The next step should be to run a larger batch with the same protocol and compare more mechanics against the no-op baseline, especially to identify mechanics that improve depth without increasing balance gap.

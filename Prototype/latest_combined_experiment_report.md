# Latest Combined Experiment Report

## Run Metadata

- Date: `2026-04-13`
- Repository: `DesignVoyager`
- Prototype: `Prototype/`
- Evaluation protocol:
  - Board:
    - Balance: `12` games of `MCTS(low) vs MCTS(low)`
    - Depth: `12` games of `MCTS(strong) vs MCTS(weak)`
  - Card:
    - Balance: `16` games of `MCTS(low) vs MCTS(low)`
    - Depth: `16` games of `MCTS(strong) vs MCTS(weak)`

## Commands Used

```powershell
python Prototype\main.py --game board --iterations 3 --top-k 3 --user-prompt "Propose a new board mechanic that improves decision-making without strongly favoring one player."
python Prototype\main.py --game card --iterations 3 --top-k 3 --user-prompt "Propose a new card mechanic that improves decision-making without strongly favoring one player."
```

## Board Experiment

### Summary

- Final accepted by verification: `3 / 3`
- Newly stored in board library: `1 / 3`
- Two accepted mechanics were rejected by the library as near-duplicates of existing entries.

### Runtime Reports Used

- [board_iter01_symmetric_adjacent_flip_on_placement_revised.json](runtime_reports/board_iter01_symmetric_adjacent_flip_on_placement_revised.json)
- [board_iter02_diagonal_capture_on_placement_initial.json](runtime_reports/board_iter02_diagonal_capture_on_placement_initial.json)
- [board_iter03_line_link_bonus_on_placement_symmetric_revised.json](runtime_reports/board_iter03_line_link_bonus_on_placement_symmetric_revised.json)

### Results Table

| Iteration | Final Mechanic | Verification | Stored in Library | Playability | Balance Gap | Depth | Aggregate |
|---|---|---|---|---:|---:|---:|---:|
| 1 | `symmetric_adjacent_flip_on_placement` | Accept | No, duplicate of existing `adjacent_flip_on_placement` | 1.000 | 0.000 | 0.667 | 0.834 |
| 2 | `diagonal_capture_on_placement` | Accept | No, duplicate of existing `diagonal_capture_on_placement` | 1.000 | 0.000 | 0.500 | 0.750 |
| 3 | `line_link_bonus_on_placement_symmetric` | Accept | Yes | 1.000 | 0.333 | 0.833 | 0.750 |

### Interpretation

The board pipeline remained fully playable and produced interpretable metrics. The strongest fairness profile appeared in `symmetric_adjacent_flip_on_placement`, which matched the best balance score in the run while maintaining moderate depth. The most strategically aggressive accepted board mechanic was `line_link_bonus_on_placement_symmetric`, which reached `depth = 0.833` but also introduced a larger balance gap of `0.333`.

The main limitation of this board run was novelty rather than runtime quality. Two accepted mechanics were too similar to already accepted entries and therefore did not expand the library.

## Card Experiment

### Summary

- Final accepted by verification: `3 / 3`
- Newly stored in card library: `3 / 3`
- Card metrics were substantially more stable than in the earlier baseline experiments.

### Runtime Reports Used

- [card_iter01_ace_of_choice_lockstep_initial.json](runtime_reports/card_iter01_ace_of_choice_lockstep_initial.json)
- [card_iter02_nearby_swap_on_6_initial.json](runtime_reports/card_iter02_nearby_swap_on_6_initial.json)
- [card_iter03_corner_guard_on_1_initial.json](runtime_reports/card_iter03_corner_guard_on_1_initial.json)

### Results Table

| Iteration | Final Mechanic | Verification | Stored in Library | Playability | Balance Gap | Depth | Aggregate |
|---|---|---|---|---:|---:|---:|---:|
| 1 | `ace_of_choice_lockstep` | Accept | Yes | 1.000 | 0.000 | 0.812 | 0.906 |
| 2 | `nearby_swap_on_6` | Accept | Yes | 1.000 | 0.000 | 0.812 | 0.906 |
| 3 | `corner_guard_on_1` | Accept | Yes | 1.000 | 0.188 | 0.688 | 0.750 |

### Interpretation

The card pipeline produced stronger results than the earlier card experiments. All three candidates were fully playable, all were accepted, and all were registered into the card mechanic library. The best two mechanics, `ace_of_choice_lockstep` and `nearby_swap_on_6`, both achieved `balance_gap = 0.000` and `depth = 0.812`, which is a clear improvement over the previous card baseline instability.

This supports the recent card-metric changes: symmetric initial hands, card-specific playtest budgets, and seat-corrected evaluation reduced environmental noise enough for card results to become usable.

## Overall Conclusions

1. The full research pipeline is operational for both board and card modes.
2. Board mode remains the more mature evaluation domain, but novelty pressure is now the bigger issue because the library already contains many similar mechanics.
3. Card mode improved substantially after the metric/performance changes and now produces acceptable balance/depth signals.
4. Library registration is now aligned with runtime acceptance rules:
   - verification decides `accept / revise / discard`
   - only accepted and non-duplicate mechanics are actually stored in the library
   - the dashboard library view now reflects the accepted library files rather than a separate dashboard-only cache

## Library State After This Run

- Board library file: [library.json](library.json)
- Card library file: [library_card.json](library_card.json)

Current counts after this run:

- Board library: `11` mechanics
- Card library: `6` mechanics

## Recommended Next Step

The next step should be to run a novelty-focused board batch with a stricter prompt that explicitly avoids the existing accepted mechanic families, while continuing to monitor whether the improved card baseline remains stable across repeated runs.

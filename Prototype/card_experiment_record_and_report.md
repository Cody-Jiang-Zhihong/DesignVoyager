# Card Experiment Record and Report

## Experiment Record

### Setup

- Game: `card`
- Evaluation budget:
  - Balance: 12 games of `MCTS(low) vs MCTS(low)`
  - Depth: 12 games of `MCTS(strong) vs MCTS(weak)`
- Stage: `Stage 1 - Simple`
- Context size: `top-k = 1`

### Runtime Reports Used

- [card_iter00_noop_card_mechanic_initial.json](runtime_reports/card_iter00_noop_card_mechanic_initial.json)
- [card_iter01_last_card_lockout_initial.json](runtime_reports/card_iter01_last_card_lockout_initial.json)
- [card_iter01_echo_combo_rule_revised.json](runtime_reports/card_iter01_echo_combo_rule_revised.json)
- [card_iter01_temporary_double_play_buff_initial.json](runtime_reports/card_iter01_temporary_double_play_buff_initial.json)
- [card_iter01_one_turn_parity_shield_after_odd_play_revised.json](runtime_reports/card_iter01_one_turn_parity_shield_after_odd_play_revised.json)
- [card_iter01_last_card_bonus_bluff_initial.json](runtime_reports/card_iter01_last_card_bonus_bluff_initial.json)
- [card_iter01_hand_size_parity_lucky_flip_revised.json](runtime_reports/card_iter01_hand_size_parity_lucky_flip_revised.json)

### Results Table

| Run | Prompt Intent | Final Mechanic | Playability | Balance Gap | Depth | Aggregate | P1 Win Rate | P2 Win Rate | Strong Win Rate | Weak Win Rate |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | No-op control | `noop_card_mechanic` | 1.000 | 0.500 | -0.083 | 0.250 | 0.250 | 0.750 | 0.417 | 0.500 |
| Run 1 | Symmetric prompt, initial | `last_card_lockout` | 1.000 | 0.333 | 0.167 | 0.417 | 0.667 | 0.333 | 0.583 | 0.417 |
| Run 1 | Symmetric prompt, revised | `echo_combo_rule` | 1.000 | 0.417 | 0.250 | 0.416 | 0.667 | 0.250 | 0.583 | 0.333 |
| Run 2 | Biased prompt, initial | `temporary_double_play_buff` | 1.000 | 0.167 | 0.000 | 0.416 | 0.583 | 0.417 | 0.500 | 0.500 |
| Run 2 | Biased prompt, revised | `one_turn_parity_shield_after_odd_play` | 1.000 | 0.667 | 0.500 | 0.416 | 0.833 | 0.167 | 0.750 | 0.250 |
| Run 3 | Strategic prompt, initial | `last_card_bonus_bluff` | 1.000 | 0.250 | 0.250 | 0.500 | 0.583 | 0.333 | 0.583 | 0.333 |
| Run 3 | Strategic prompt, revised | `hand_size_parity_lucky_flip` | 1.000 | 0.833 | -0.167 | 0.084 | 0.917 | 0.083 | 0.417 | 0.583 |

### Notes

- The card-game pipeline ran successfully for all tested prompts.
- All final candidates were fully playable.
- None of the tested card mechanics produced a strong combination of fairness and strategic depth under the current evaluation settings.
- Several revised card mechanics became more imbalanced than their initial versions.

## Experiment Report

This experiment evaluated the card-game version of DesignVoyager using the same small MCTS-based protocol used for the board-game tests. Each final candidate mechanic was tested with 12 balance games using low-budget MCTS on both sides, and 12 depth games using strong-budget MCTS against weak-budget MCTS. The goal was to verify that the generalized pipeline works on a second game type and to observe how the current balance and depth metrics behave in the card setting.

The card-game pipeline ran end to end without runtime failures, and all final recorded candidates achieved perfect playability. This confirms that the generalized implementation can generate, compile, simulate, and evaluate mechanics for a non-board game. However, the metric profile for the card game was clearly weaker than for the board game.

The no-op baseline already showed a substantial balance gap (`0.500`) and a negative depth score (`-0.083`), which suggests that the current card-game evaluation environment is noisier or less well calibrated than the board-game environment. This baseline matters because it means some instability is present even before additional mechanics are introduced.

Among the tested candidates, `last_card_bonus_bluff` produced the strongest initial strategic result, with `depth = 0.250` and `balance_gap = 0.250`, but its aggregate score remained only `0.500`, which was below the acceptance threshold. Other mechanics either preserved moderate depth while becoming too imbalanced, or reduced fairness without creating a clear strategic improvement. The most extreme case was `hand_size_parity_lucky_flip`, which had `balance_gap = 0.833` and `depth = -0.167`, making it both unfair and strategically weak under the current metric.

Overall, this experiment shows that the card-game pipeline is functional, but its evaluation quality is not yet as reliable as the board-game version. The next step should be to tune the card-game rules, MCTS budgets, or scoring interpretation so that the baseline itself is more stable. At the current stage, the card game is best presented as evidence that the system has been generalized to another game type, rather than as the strongest evaluation domain for demonstrating mechanic quality.

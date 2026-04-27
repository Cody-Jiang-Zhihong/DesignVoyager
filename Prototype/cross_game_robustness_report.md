# Cross-Game Robustness Pass

Tested mechanics: 10

## Summary

- robust: 1
- context_sensitive: 3
- non_robust: 6

## Results

### safe_exact_12_block - context_sensitive
- compatible: card
- failed: board
- pass_rate: 0.500; positive_rate: 0.500; mean_relative_score: 0.001
- board: discard / negative_relative_gain / relative=-0.033
- card: accept / positive_relative_gain / relative=0.035

### diagonal_capture_on_placement - non_robust
- compatible: none
- failed: board, card
- pass_rate: 0.000; positive_rate: 0.000; mean_relative_score: -0.037
- board: discard / negative_relative_gain / relative=-0.075
- card: discard / no_state_change / relative=0.000

### diagonal_freeze_on_placement - non_robust
- compatible: none
- failed: board, card
- pass_rate: 0.000; positive_rate: 0.000; mean_relative_score: -0.092
- board: discard / negative_relative_gain / relative=-0.184
- card: discard / no_state_change / relative=0.000

### orthogonal_swap_on_capture - non_robust
- compatible: none
- failed: board, card
- pass_rate: 0.000; positive_rate: 0.000; mean_relative_score: -0.017
- board: discard / negative_relative_gain / relative=-0.033
- card: discard / no_state_change / relative=0.000

### orthogonal_block_on_placement - context_sensitive
- compatible: board
- failed: card
- pass_rate: 0.500; positive_rate: 0.500; mean_relative_score: 0.017
- board: accept / positive_relative_gain / relative=0.034
- card: discard / no_state_change / relative=0.000

### adjacent_capture_on_placement_symmetric - non_robust
- compatible: none
- failed: board, card
- pass_rate: 0.000; positive_rate: 0.000; mean_relative_score: 0.000
- board: discard / negative_relative_gain / relative=0.000
- card: discard / no_state_change / relative=0.000

### diagonal_flip_adjacent_on_placement - non_robust
- compatible: none
- failed: board, card
- pass_rate: 0.000; positive_rate: 0.000; mean_relative_score: -0.004
- board: discard / negative_relative_gain / relative=-0.008
- card: discard / no_state_change / relative=0.000

### wild_pause_action - robust
- compatible: board, card
- failed: none
- pass_rate: 1.000; positive_rate: 1.000; mean_relative_score: 0.068
- board: accept / positive_relative_gain / relative=0.034
- card: accept / positive_relative_gain / relative=0.102

### ace_of_choice_lockstep - non_robust
- compatible: none
- failed: board, card
- pass_rate: 0.000; positive_rate: 0.000; mean_relative_score: -0.043
- board: discard / no_state_change / relative=0.000
- card: discard / negative_relative_gain / relative=-0.086

### nearby_swap_on_6 - context_sensitive
- compatible: card
- failed: board
- pass_rate: 0.500; positive_rate: 0.500; mean_relative_score: 0.024
- board: discard / no_state_change / relative=0.000
- card: accept / positive_relative_gain / relative=0.048

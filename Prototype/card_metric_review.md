# Card Playtest Metric Review

## Problem Summary

The original card-game baseline was not trustworthy enough for research use.

From the earlier experiment record in [card_experiment_record_and_report.md](./card_experiment_record_and_report.md):

- baseline `balance_gap = 0.500`
- baseline `depth = -0.083`

That profile meant the environment itself was unstable before any new mechanic was added. In practice, card metrics were being dominated by setup noise rather than by mechanic quality.

## Root Causes

The main problems were structural:

1. The two players were starting with independently random hands.
2. The card playtest used the same MCTS budgets and game counts as the board game, even though the card environment is smaller and noisier.
3. Card balance was still sensitive to starting-seat effects, because the score metric only compared `Player 1` vs `Player 2` win rates.

## Changes Made

### 1. Symmetric initial hands for card games

In [card_game.py](./card_game.py), both players now receive the same sampled starting hand instead of separate random hands.

This removes a large source of baseline variance and makes balance metrics reflect the mechanic and decision process more directly.

### 2. Card-specific playtest budgets

In [playtest_module.py](./playtest_module.py), card games now use their own evaluation settings:

- `CARD_N_GAMES_BALANCE = 16`
- `CARD_N_GAMES_DEPTH = 16`
- `CARD_BALANCE_MCTS_SIMS = 40`
- `CARD_DEPTH_STRONG_SIMS = 96`
- `CARD_DEPTH_WEAK_SIMS = 24`

This gives the card evaluation more samples and a clearer strong-vs-weak agent separation than the previous board-shared defaults.

### 3. Starting-player correction only for card mode

Card balance/depth collection now alternates the starting player during playtest, while board mode keeps its original behavior.

This reduces first-player bias in the card metric without destabilizing the board baseline.

## Validation

After the changes, a no-op validation run produced:

- Card baseline: `playability = 1.0`, `balance_gap = 0.188`, `depth = 0.688`, `aggregate = 0.750`
- Board baseline: `playability = 1.0`, `balance_gap = 0.167`, `depth = 0.833`, `aggregate = 0.833`

These numbers are still not perfect, but they are much more usable than the previous card baseline. The main improvement is that the card environment no longer begins in an obviously broken metric state.

## Interpretation

The card pipeline is now in a better place for iterative research:

- `playability` remains stable
- `balance_gap` is no longer dominated by random starting hands
- `depth` is now positive and interpretable

The remaining limitation is that card metrics are still somewhat noisier than board metrics. That is acceptable for the current stage, but it means board remains the stronger demonstration domain while card remains the domain that still needs calibration.

## Next Recommendation

If card metrics still need to be tightened further, the next reasonable changes would be:

1. log `first_player_win_rate` explicitly in the runtime report
2. increase card evaluation counts again for final-report runs
3. redesign the card rule set itself if repeated baselines still show persistent seat bias

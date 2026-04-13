# DesignVoyager --- Project Execution Plan

## Current Repo State

The active implementation now lives in `Prototype/`.

Current `Prototype/` capabilities:

- Multi-game pipeline with `board` and `card` modes
- MCTS-based playtesting for both game modes
- Cross-platform subprocess-based playtest execution for Windows and macOS
- FastAPI dashboard under `Prototype/web/`
- Runtime self-verification JSON reports under `Prototype/runtime_reports/`
- Sample board experiment write-up in `Prototype/board_experiment_record_and_report.md`
- Sample card experiment write-up in `Prototype/card_experiment_record_and_report.md`
- Latest combined board/card experiment report in `Prototype/latest_combined_experiment_report.md`
- Card metric review in `Prototype/card_metric_review.md`

Useful entry points:

```bash
python Prototype/main.py --game board
python Prototype/main.py --game card
python Prototype/demo_main.py --game board
python Prototype/demo_main.py --game card
cd Prototype && python -m uvicorn web.app:app --reload --port 8000
```

Current Week 3 status:

- End-to-end pipeline is integrated for both game modes
- Dashboard is connected to the active playtest pipeline
- Only accepted, non-duplicate mechanics are registered into the active library
- Dashboard library view is now driven by the accepted library files, not a separate dashboard-only source

## Overview

This repository contains the implementation of **DesignVoyager**, a
lifelong learning agent for automated game design using LLM-generated
mechanics, iterative playtesting, and a persistent mechanic library.

Our goal is to **complete a working end-to-end system by Week 5**,
leaving buffer time for evaluation, polishing, and presentation.

------------------------------------------------------------------------

## Week 1 --- Setup & Alignment

**Goal: Define system interfaces & baseline pipeline**

### Proposal Module --- Morgan

-   Define prompt format for mechanic generation\
-   Setup GPT → Python generation pipeline

### Playtest Module --- Cody

-   Setup Boardwalk environment\
-   Implement basic MCTS evaluation loop

### Self-Verification Module --- Ruimeng

-   Define evaluation metrics (playability, balance, depth)\
-   Design acceptance criteria

### Mechanism Library --- Ziyi

-   Design data structure for mechanic storage\
-   Implement retrieval interface (top-k)

### Integration --- Benjamin & Cody

-   Define module interfaces\
-   Connect minimal end-to-end pipeline (prototype v0)

------------------------------------------------------------------------

## Week 2 --- Core Module Implementation

**Goal: Each module becomes independently functional**

-   Proposal: Generate valid mechanics + basic error handling\
-   Playtest: Run simulations and output metrics\
-   Self-Verification: Implement scoring and decision logic\
-   Library: Store and retrieve mechanics with metadata

**Deliverable:** All modules runnable independently

------------------------------------------------------------------------

## Week 3 --- Full Pipeline Integration

**Goal: Build first working DesignVoyager loop**

-   Connect all modules into iterative pipeline\
-   Implement:
    -   proposal → playtest → verification → library\
    -   repair loop (retry on failure)

**Deliverable:** End-to-end system (v1)

------------------------------------------------------------------------

## Week 4 --- Stabilization & Iteration

**Goal: Improve system quality and robustness**

-   Debug invalid mechanics and runtime issues\
-   Tune:
    -   prompts\
    -   evaluation weights\
-   Run medium-scale experiments (20--30 iterations)

**Deliverable:** Stable system (v2)

------------------------------------------------------------------------

## Week 5 --- Finalization

**Goal: Complete core system early**

-   Run full experiments\
-   Compare with baselines (stateless GPT / evolutionary)\
-   Collect metrics:
    -   playability\
    -   balance\
    -   strategic depth

**Deliverable:** Final working system + results

------------------------------------------------------------------------

## Week 6--7 --- Buffer & Presentation

**Goal: Polish and prepare for demo**

-   Improve demo quality\
-   Prepare slides & visualizations\
-   Optimize runtime if needed

------------------------------------------------------------------------

## Key Principle

> Each module is developed independently, but the core innovation comes
> from their integration into a closed iterative learning loop.

------------------------------------------------------------------------

## System Pipeline

    GPT (Proposal)
        ↓
    Mechanic (Python)
        ↓
    Boardwalk (Execution)
        ↓
    MCTS (Playtest)
        ↓
    Evaluation (Self-Verification)
        ↓
    Mechanic Library (Memory)
        ↓
    Next Iteration

------------------------------------------------------------------------

## Contributors

-   Morgan Waddington --- Proposal Module\
-   Cody Jiang --- Playtest Module & Integration\
-   Ruimeng Yang --- Self-Verification Module\
-   Ziyi Zhu --- Mechanism Library\
-   Benjamin Tian --- Integration

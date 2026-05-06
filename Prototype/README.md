# DesignVoyager Prototype

DesignVoyager is a research prototype for automated game mechanic design.
It uses an LLM to propose mechanics, evaluates them through automated play,
stores accepted mechanics in a persistent library, and exposes the workflow
through an interactive dashboard.

## Current scope

- Board and card game pipelines
- Baseline-aware verification and revision loop
- Library analytics view
- AI vs AI showcase
- Play vs AI
- Phone mode
- Pair Lab

## Tech stack

- Python
- FastAPI + WebSocket dashboard
- OpenAI API for proposal and alignment checks
- Embedding-based mechanic retrieval
- MCTS / minimax playtesting

## Run the prototype

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the CLI pipeline:

```powershell
python main.py --game board
python main.py --game card
```

Run the dashboard:

```powershell
python -m uvicorn web.app:app --reload --host 0.0.0.0 --port 8080
```

Open:

- Local dashboard: `http://127.0.0.1:8080`
- Phone page on this machine: `http://127.0.0.1:8080/phone`

For phone testing on the same Wi-Fi, use your laptop's LAN IP instead of
`127.0.0.1`. If local network access is blocked, use ngrok.

## Important files

- `main.py`: CLI pipeline entry point
- `proposal_module.py`: LLM proposal + revision
- `mechanic_library.py`: persistent library + retrieval
- `playtest_module.py`: simulation and metrics
- `verification_module.py`: accept / revise / discard
- `web/app.py`: FastAPI server
- `web/pipeline_runner.py`: dashboard pipeline adapter

## Notes

- The active implementation is this `Prototype/` directory.
- Older duplicated files at the repository root were removed so imports and
  documentation point to one source of truth.

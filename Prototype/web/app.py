"""
app.py
======
DesignVoyager Web Dashboard

FastAPI application with a WebSocket endpoint that streams
pipeline events to the browser in real time.

Run with:
    cd Prototype
    uvicorn web.app:app --reload --port 8000

Then open http://localhost:8000
"""

import asyncio
import json
import queue
import threading
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="DesignVoyager Dashboard")
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Serve static files (HTML, CSS, JS)
_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/")
async def root():
    """Serve the dashboard page."""
    return FileResponse(os.path.join(_static_dir, "index.html"))


@app.get("/api/library-cards")
async def get_library_cards():
    """
    Return accepted mechanics from the real library files, merged with optional
    dashboard replay metadata when available.
    """
    cards = _build_library_cards()
    return JSONResponse(content=cards)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    Single WebSocket connection per run.

    Protocol:
      Client sends: {"type": "start_run", "data": {"game_name", "iterations", "top_k", "user_prompt"}}
      Server sends: stream of {"type": "...", "data": {...}} events
      Client sends: {"type": "stop_run"} to cancel early
    """
    await ws.accept()

    try:
        while True:
            # Wait for the client to send a start_run message
            raw = await ws.receive_text()
            msg = json.loads(raw)

            if msg.get("type") != "start_run":
                await ws.send_json({"type": "error", "data": {
                    "message": f"Expected start_run, got {msg.get('type')}"
                }})
                continue

            data       = msg.get("data", {})
            game_name  = data.get("game_name", "board")
            iterations = int(data.get("iterations", 3))
            top_k      = int(data.get("top_k", 3))
            user_prompt = data.get("user_prompt", "")

            # Event queue: pipeline thread writes, this coroutine reads
            event_queue = queue.Queue()
            stop_event  = threading.Event()

            # Import here to avoid circular imports at module load
            from web.pipeline_runner import EventEmitter, run_web_pipeline

            emitter = EventEmitter(event_queue)

            # Run the pipeline in a background thread
            pipeline_thread = threading.Thread(
                target=_run_pipeline_thread,
                args=(emitter, game_name, iterations, top_k, stop_event, user_prompt),
                daemon=True,
            )
            pipeline_thread.start()

            # Stream events to the client until the pipeline finishes
            try:
                await _stream_events(ws, event_queue, pipeline_thread, stop_event)
            except WebSocketDisconnect:
                stop_event.set()
                return

    except WebSocketDisconnect:
        pass


def _run_pipeline_thread(emitter, game_name, iterations, top_k, stop_event, user_prompt):
    """
    Wrapper that runs the pipeline and catches any unhandled exceptions,
    sending them as error events so the browser knows what happened.
    """
    # Change to the project root so library.json paths resolve correctly
    os.chdir(PROJECT_DIR)

    from web.pipeline_runner import run_web_pipeline
    try:
        run_web_pipeline(emitter, game_name, iterations, top_k, stop_event, user_prompt)
    except Exception as e:
        emitter.emit("error", {"message": f"Pipeline crashed: {e}"})


async def _stream_events(ws, event_queue, pipeline_thread, stop_event):
    """
    Pull events from the queue and send them over the WebSocket.
    Also listens for stop_run messages from the client.
    """
    while True:
        # Check for incoming messages (stop_run) without blocking
        try:
            raw = await asyncio.wait_for(
                _receive_or_none(ws),
                timeout=0.05,
            )
            if raw is not None:
                msg = json.loads(raw)
                if msg.get("type") == "stop_run":
                    stop_event.set()
                    await ws.send_json({"type": "error", "data": {
                        "message": "Run stopped by user."
                    }})
        except asyncio.TimeoutError:
            pass

        # Drain all available events from the queue
        events_sent = False
        while True:
            try:
                event = event_queue.get_nowait()
                await ws.send_json(event)
                events_sent = True

                # If this was the final event, we're done
                if event.get("type") in ("run_complete", "error"):
                    return
            except queue.Empty:
                break

        # If the pipeline thread has died and the queue is empty, stop
        if not pipeline_thread.is_alive() and event_queue.empty():
            return

        # Small sleep to avoid busy-waiting
        if not events_sent:
            await asyncio.sleep(0.1)


async def _receive_or_none(ws):
    """Try to receive a WebSocket message; returns None if nothing available."""
    return await ws.receive_text()


def _load_json_file(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _replay_metadata_key(card: dict):
    return (
        card.get("game_type", ""),
        card.get("mechanic_name", ""),
        card.get("iteration"),
    )


def _build_library_cards():
    board_library = _load_json_file(os.path.join(PROJECT_DIR, "library.json"), [])
    card_library = _load_json_file(os.path.join(PROJECT_DIR, "library_card.json"), [])
    replay_cards = _load_json_file(os.path.join(PROJECT_DIR, "library_cards.json"), [])

    replay_by_key = {}
    replay_by_name = {}
    for replay_card in replay_cards:
        replay_by_key[_replay_metadata_key(replay_card)] = replay_card
        replay_by_name[(replay_card.get("game_type", ""), replay_card.get("mechanic_name", ""))] = replay_card

    merged_cards = []
    for game_type, entries in (("board", board_library), ("card", card_library)):
        for entry in entries:
            base_card = {
                "game_type": game_type,
                "mechanic_name": entry.get("mechanic_name", ""),
                "mechanic_type": entry.get("mechanic_type", ""),
                "description": entry.get("description", ""),
                "justification": entry.get("justification", ""),
                "python_code": entry.get("python_code", ""),
                "scores": entry.get("scores", {}),
                "verification": entry.get("verification", {}),
                "robustness": entry.get("robustness", {}),
                "iteration": entry.get("iteration"),
                "runtime_report": None,
                "replay": None,
            }
            replay_card = (
                replay_by_key.get(_replay_metadata_key(base_card))
                or replay_by_name.get((game_type, base_card["mechanic_name"]))
            )
            if replay_card:
                base_card.update({
                    "description": replay_card.get("description", base_card["description"]),
                    "verification": replay_card.get("verification", base_card["verification"]),
                    "robustness": replay_card.get("robustness", base_card["robustness"]),
                    "replay": replay_card.get("replay"),
                    "runtime_report": replay_card.get("runtime_report"),
                })
            merged_cards.append(base_card)

    merged_cards.sort(
        key=lambda card: (
            card.get("game_type", ""),
            card.get("iteration") if card.get("iteration") is not None else -1,
            card.get("mechanic_name", ""),
        )
    )
    return merged_cards

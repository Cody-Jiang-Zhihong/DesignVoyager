# DesignVoyager

The active project lives in `Prototype/`.

Use this repository root only as a container for the current prototype.
The older duplicate source files that used to exist at the root level have
been removed to avoid confusion.

## Main entry points

```powershell
cd Prototype
python main.py --game board
python main.py --game card
python -m uvicorn web.app:app --reload --host 0.0.0.0 --port 8080
```

## Main docs

- Active implementation: `Prototype/`
- Dashboard frontend: `Prototype/web/static/`
- Dashboard backend: `Prototype/web/app.py`
- Primary project README: `Prototype/README.md`

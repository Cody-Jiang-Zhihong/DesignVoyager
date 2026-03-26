# Proposal Module — Morgan's Guide

## What is this file?

`proposal_module.py` is your contribution to the DesignVoyager project.
It handles the very first step in every loop: asking GPT-4 to come up
with a new game mechanic and write it as Python code.

---

## How it works (plain English)

1. The system gives your module two things:
   - The **current game** (a text description of what the game looks like so far)
   - A few **examples of mechanics that already worked** (from Benjamin/Ziyi's library)

2. Your module bundles those into a prompt and sends it to GPT-4.

3. GPT-4 responds with a **new mechanic** — including a name, description,
   and Python code that implements it.

4. Your module checks if the Python code is valid.
   - If yes → return the mechanic. Done!
   - If no → tell GPT-4 what broke and ask it to fix it (up to 3 tries).
   - If still broken after 3 tries → give up, return None.

---

## How to set up and run it

### Step 1 — Install the required library

Open a terminal and run:
```
pip install -r requirements.txt
```

### Step 2 — Set your API key

**If using NYU Portkey (recommended — it's free):**
Ask your instructor for the Portkey base URL and API key, then run:
```
export OPENAI_API_KEY="your-portkey-key"
export OPENAI_BASE_URL="https://..."
```

**If using your personal OpenAI key:**
```
export OPENAI_API_KEY="sk-..."
```
(On Windows, use `set` instead of `export`)

### Step 3 — Test it

Run the file directly to see it in action:
```
python proposal_module.py
```

It will send a test game description to GPT-4 and print the mechanic it proposes.

---

## How your teammates will use your module

Your teammates just need to import one function:

```python
from proposal_module import propose_mechanic

result = propose_mechanic(game_skeleton, retrieved_mechanics)
```

`result` will be a dictionary like this:
```python
{
    "mechanic_name": "bonus_move",
    "mechanic_type": "movement",
    "description": "A player who captures a piece gets an extra turn.",
    "justification": "Rewards aggressive play and increases strategic depth.",
    "python_code": "def bonus_move(game_state, **kwargs):\n    ..."
}
```

Or `None` if GPT-4 couldn't produce working code after 3 tries.

---

## Questions?

If anything is confusing, ask your teammate Cody (who handles the next step —
playtesting), or ask Claude for help!

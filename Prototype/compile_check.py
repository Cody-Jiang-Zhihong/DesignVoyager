"""
compile_check.py
================
DesignVoyager - Compile Check Module

Checks that proposed mechanic code parses and runs on a realistic game state.
This version is game-agnostic: callers may provide a dummy_state from the
active game implementation.
"""

import ast
import copy
import numpy as np


def check_syntax(code: str) -> tuple:
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError on line {e.lineno}: {e.msg}"


def check_runtime(code: str, dummy_state: dict = None) -> tuple:
    if dummy_state is None:
        from base_game import BaseGame
        dummy_state = BaseGame.create().get_dummy_state()

    required_keys = set(dummy_state.keys())
    namespace = {"np": np, "numpy": np}

    try:
        exec(code, namespace)
    except Exception as e:
        return False, f"Code failed to load: {type(e).__name__}: {e}"

    tree = ast.parse(code)
    fn_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    if not fn_names:
        return False, "No function definition found in the code."

    fn_name = fn_names[0]
    fn = namespace.get(fn_name)
    if fn is None:
        return False, f"Function '{fn_name}' not found after exec."

    try:
        result = fn(copy.deepcopy(dummy_state))
    except Exception as e:
        return False, f"Function crashed at runtime: {type(e).__name__}: {e}"

    if not isinstance(result, dict):
        return False, f"Function must return a dict but returned {type(result).__name__}."

    missing = required_keys - set(result.keys())
    if missing:
        return False, f"Returned dict is missing required keys: {sorted(missing)}"

    return True, ""


def compile_check(mechanic: dict, dummy_state: dict = None) -> tuple:
    code = mechanic.get("python_code", "")
    name = mechanic.get("mechanic_name", "unknown")

    print(f"[CompileCheck] Checking '{name}'...")

    ok, err = check_syntax(code)
    if not ok:
        print(f"  [CompileCheck] x Syntax error: {err}")
        return False, err

    ok, err = check_runtime(code, dummy_state=dummy_state)
    if not ok:
        print(f"  [CompileCheck] x Runtime error: {err}")
        return False, err

    print("  [CompileCheck] passed")
    return True, ""


def load_mechanic_fn(code: str):
    namespace = {"np": np, "numpy": np}
    exec(code, namespace)
    tree = ast.parse(code)
    fn_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    if not fn_names:
        return None
    return namespace.get(fn_names[0])

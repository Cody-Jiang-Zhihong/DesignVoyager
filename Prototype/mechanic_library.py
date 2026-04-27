"""
mechanic_library.py
===================
DesignVoyager — Mechanic Library

Persistent memory for the system. Stores validated mechanics in a
JSON file (library.json) so they survive between runs.

Each mechanic is stored with:
  - mechanic_name, mechanic_type, description, justification, python_code
  - scores: playability, balance, depth, aggregate (from playtesting)
  - verification: structured self-verification output for accepted runs
  - robustness: cross-game robustness label and compatibility metadata
  - iteration: which loop iteration it was accepted on
  - embedding: OpenAI vector for semantic retrieval (text-embedding-3-small)

Retrieval
---------
retrieve(k, query=None)
  - With query   : semantic similarity (cosine) between the query and each
                   mechanic's embedding, blended with aggregate score.
                   A light diversity filter still avoids returning all
                   mechanics of the same type.
  - Without query : diversity-first fallback (one per type, highest score).
"""

import json
import os
import copy
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

LIBRARY_FILE        = "library.json"
EMBEDDING_MODEL     = "text-embedding-3-small"
SEMANTIC_WEIGHT     = 0.75   # how much semantic similarity matters vs aggregate score
AGGREGATE_WEIGHT    = 0.25
SCORE_THRESHOLD     = 0.25  # minimum combined score for a mechanic to be recalled
DIVERSITY_PENALTY   = 0.75    # penalty multiplier for mechanics with already-selected types
SIMILARITY_THRESHOLD = 0.85   # max allowed similarity when adding new mechanic to library
MAX_CONTEXT_USES    = 3     # a mechanic can appear as context at most this many times per run

DEFAULT_ROBUSTNESS = {
    "label": "untested",
    "compatible_game_types": [],
    "failed_game_types": [],
    "tested_games": 0,
    "pass_rate": None,
    "positive_rate": None,
    "mean_relative_score": None,
    "hard_failure_rate": None,
}

_client = OpenAI(
    api_key  = os.getenv("OPENAI_API_KEY", ""),
    base_url = os.getenv("OPENAI_BASE_URL", None),
)


# ── Embedding helpers ─────────────────────────────────────────────────────────

def _embed(text: str) -> list:
    """
    Call OpenAI to get a vector embedding for a piece of text.
    Returns an empty list if the call fails (graceful degradation).
    text-embedding-3-small costs ~$0.00002 per 1K tokens — essentially free.
    """
    try:
        response = _client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        return response.data[0].embedding
    except Exception as e:
        print(f"[Library] Embedding failed (will use fallback): {e}")
        return []


def _cosine(a: list, b: list) -> float:
    """Cosine similarity between two embedding vectors."""
    if not a or not b:
        return 0.0
    arr_a = np.array(a, dtype=float)
    arr_b = np.array(b, dtype=float)
    denom = np.linalg.norm(arr_a) * np.linalg.norm(arr_b)
    return float(np.dot(arr_a, arr_b) / denom) if denom > 0 else 0.0


def _mechanic_text(m: dict) -> str:
    """Short text that represents a mechanic for embedding."""
    return (
        f"{m.get('mechanic_name', '')} "
        f"{m.get('mechanic_type', '')} "
        f"{m.get('description', '')} "
        f"{m.get('justification', '')}"
    )


def _build_verification_metadata(mechanic: dict) -> dict:
    output = copy.deepcopy(mechanic.get("_verification_output") or {})
    if not output:
        return {
            "decision": "accept",
            "reason": "legacy_accept",
            "relative_score": None,
            "overall_score": None,
            "failure_modes": [],
            "absolute_metrics": {},
            "delta_metrics": {},
            "trigger_stats": {},
        }

    return {
        "decision": output.get("decision", "accept"),
        "reason": output.get("reason", ""),
        "relative_score": output.get("relative_score"),
        "overall_score": output.get("overall_score"),
        "failure_modes": output.get("failure_modes", []),
        "absolute_metrics": output.get("absolute_metrics", {}),
        "delta_metrics": output.get("delta_metrics", {}),
        "trigger_stats": output.get("trigger_stats", {}),
        "metadata_for_library": output.get("metadata_for_library", {}),
    }


def _build_robustness_metadata(mechanic: dict) -> dict:
    raw = copy.deepcopy(mechanic.get("_cross_game_verification") or {})
    if not raw:
        return copy.deepcopy(DEFAULT_ROBUSTNESS)

    metadata = raw.get("metadata_for_library", raw)
    return {
        "label": metadata.get("robustness_label", raw.get("robustness_label", "untested")),
        "compatible_game_types": metadata.get("compatible_game_types", raw.get("compatible_game_types", [])),
        "failed_game_types": metadata.get("failed_game_types", raw.get("failed_game_types", [])),
        "tested_games": metadata.get("tested_games", raw.get("tested_games", 0)),
        "pass_rate": metadata.get("pass_rate", raw.get("pass_rate")),
        "positive_rate": metadata.get("positive_rate", raw.get("positive_rate")),
        "mean_relative_score": metadata.get("mean_relative_score", raw.get("mean_relative_score")),
        "hard_failure_rate": metadata.get("hard_failure_rate", raw.get("hard_failure_rate")),
        "game_type_summaries": metadata.get("game_type_summaries", {}),
    }


# ── Library class ─────────────────────────────────────────────────────────────

class MechanicLibrary:
    """
    Persistent store of validated game mechanics.

    Usage:
        library = MechanicLibrary()
        library.add(mechanic_dict, scores_dict, iteration=1)

        # Semantic retrieval (preferred):
        top3 = library.retrieve(k=3, query="current game context string")

        # Diversity fallback (no query):
        top3 = library.retrieve(k=3)
    """

    def __init__(self, filepath: str = LIBRARY_FILE):
        self.filepath  = filepath
        self.mechanics = []
        self._context_use_count: dict = {}   # tracks per-run usage; not persisted to disk
        self.load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    self.mechanics = json.load(f)
                print(f"[Library] Loaded {len(self.mechanics)} mechanics from {self.filepath}")
            except Exception as e:
                print(f"[Library] Could not load library: {e}. Starting fresh.")
                self.mechanics = []
        else:
            print("[Library] No existing library found. Starting fresh.")
            self.mechanics = []

    def save(self):
        with open(self.filepath, 'w') as f:
            json.dump(self.mechanics, f, indent=2)
        print(f"[Library] Saved {len(self.mechanics)} mechanics to {self.filepath}")

    # ── Add ───────────────────────────────────────────────────────────────────

    def add(self, mechanic: dict, scores: dict, iteration: int = 0) -> bool:
        """
        Add a validated mechanic. Computes and stores an embedding for
        semantic retrieval in future iterations.
        
        Before adding, checks similarity against all existing mechanics.
        Rejects if any existing mechanic has similarity >= SIMILARITY_THRESHOLD.
        """
        mechanic_name = mechanic.get("mechanic_name", "unknown")
        new_embedding = _embed(_mechanic_text(mechanic))
        similar_entry, similarity = self.find_most_similar(
            mechanic,
            embedding=new_embedding,
            threshold=SIMILARITY_THRESHOLD,
        )
        if similar_entry is not None:
            print(f"[Library] Rejected mechanic '{mechanic_name}': "
                  f"too similar to '{similar_entry['mechanic_name']}' (similarity: {similarity:.3f})")
            return False

        verification = _build_verification_metadata(mechanic)
        if verification.get("decision") != "accept":
            print(f"[Library] Rejected mechanic '{mechanic_name}': "
                  f"verification decision is '{verification.get('decision')}'")
            return False
        
        entry = {
            "mechanic_name": mechanic_name,
            "mechanic_type": mechanic.get("mechanic_type", "other"),
            "game_type":     mechanic.get("_game_type", mechanic.get("game_type", "")),
            "description":   mechanic.get("description", ""),
            "justification": mechanic.get("justification", ""),
            "python_code":   mechanic.get("python_code", ""),
            "scores":        scores,
            "verification":  verification,
            "robustness":    _build_robustness_metadata(mechanic),
            "iteration":     iteration,
            "embedding":     new_embedding,
        }
        self.mechanics.append(entry)
        self.save()
        print(f"[Library] Added mechanic '{entry['mechanic_name']}' "
              f"(library size: {len(self.mechanics)})")
        return True

    def find_most_similar(self, mechanic: dict, embedding: list = None,
                          threshold: float = None) -> tuple:
        """
        Return the most similar existing library mechanic and its cosine similarity.

        If `threshold` is provided, only return a match when the best similarity
        meets or exceeds that threshold. Otherwise returns the best match even if
        the similarity is low.
        """
        if not self.mechanics:
            return None, 0.0

        threshold = SIMILARITY_THRESHOLD if threshold is None else threshold
        embedding = embedding if embedding is not None else _embed(_mechanic_text(mechanic))

        best_entry = None
        best_similarity = -1.0
        for existing in self.mechanics:
            existing_embedding = existing.get("embedding", [])
            similarity = _cosine(embedding, existing_embedding)
            if similarity > best_similarity:
                best_entry = existing
                best_similarity = similarity

        if best_entry is None or best_similarity < threshold:
            return None, max(best_similarity, 0.0)
        return best_entry, best_similarity

    # ── Retrieve ──────────────────────────────────────────────────────────────

    def retrieve(self, k: int = 3, query: str = None) -> list:
        """
        Retrieve up to k mechanics as context for the proposal module.

        Each mechanic can appear in context at most MAX_CONTEXT_USES times per
        run (tracked in self._context_use_count). Once all mechanics are capped,
        the counts reset so the run can continue.

        Args:
            k     : Number of mechanics to return.
            query : Free-text description of the current game context.
                    If provided, uses semantic similarity. If None, uses
                    diversity-first fallback.
        """
        if not self.mechanics:
            return []

        # Build eligible pool — exclude mechanics that hit the per-run cap
        eligible = [
            m for m in self.mechanics
            if self._context_use_count.get(m["mechanic_name"], 0) < MAX_CONTEXT_USES
        ]
        if not eligible:
            # Every mechanic has been capped — reset and start fresh
            self._context_use_count = {}
            eligible = list(self.mechanics)

        k = min(k, len(eligible))

        if query:
            selected = self._retrieve_semantic(query, k, eligible)
        else:
            selected = self._retrieve_diversity(k, eligible)

        # Record that these mechanics were used as context this iteration
        for m in selected:
            name = m["mechanic_name"]
            self._context_use_count[name] = self._context_use_count.get(name, 0) + 1

        return selected

    def _retrieve_semantic(self, query: str, k: int, pool: list) -> list:
        """
        Rank mechanics by cosine similarity to the query embedding,
        blended with their aggregate playtest score.
        Only recall mechanics with combined score > SCORE_THRESHOLD.
        Return up to k mechanics, prioritizing diversity:
        mechanics of the same type as already-selected ones get a diversity penalty.
        """
        query_emb = _embed(query)

        items = []
        for m in pool:
            sim = _cosine(query_emb, m.get("embedding", []))
            # Mechanics without an embedding get a neutral similarity score
            # so they can still appear but aren't preferred
            if not m.get("embedding"):
                sim = 0.3
            agg     = m.get("scores", {}).get("aggregate", 0.5)
            combined = SEMANTIC_WEIGHT * sim + AGGREGATE_WEIGHT * agg
            items.append({
                "mechanic": m,
                "base_score": combined,
                "adjusted_score": combined
            })

        # Filter by threshold — only consider mechanics above score threshold
        threshold_passed = [item for item in items if item["base_score"] > SCORE_THRESHOLD]

        if not threshold_passed:
            return []

        final_count = min(k, len(threshold_passed))
        selected = []
        selected_types = set()

        # Iteratively select mechanics with diversity penalty applied
        for _ in range(final_count):
            if not threshold_passed:
                break

            # Select the highest-scoring mechanic from remaining
            best_item = max(threshold_passed, key=lambda x: x["adjusted_score"])

            # Remove from candidate pool
            threshold_passed.remove(best_item)

            # Add to result
            selected.append(best_item["mechanic"])
            best_type = best_item["mechanic"].get("mechanic_type", "other")
            selected_types.add(best_type)

            # Apply diversity penalty: reduce score of remaining mechanics with same type
            for item in threshold_passed:
                item_type = item["mechanic"].get("mechanic_type", "other")
                if item_type in selected_types:
                    item["adjusted_score"] = item["base_score"] * DIVERSITY_PENALTY

        return selected

    def _retrieve_diversity(self, k: int, pool: list) -> list:
        """
        Original fallback: one mechanic per type (highest aggregate),
        then fill by overall score.
        """
        by_type = {}
        for m in pool:
            t = m.get("mechanic_type", "other")
            by_type.setdefault(t, []).append(m)

        selected = []
        for group in by_type.values():
            if len(selected) >= k:
                break
            best = max(group, key=lambda m: m.get("scores", {}).get("aggregate", 0))
            selected.append(best)

        remaining = [m for m in pool if m not in selected]
        remaining.sort(key=lambda m: m.get("scores", {}).get("aggregate", 0), reverse=True)
        selected.extend(remaining[:k - len(selected)])

        return selected[:k]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def size(self) -> int:
        return len(self.mechanics)

    def summary(self) -> str:
        if not self.mechanics:
            return "Library is empty."
        names = [m["mechanic_name"] for m in self.mechanics]
        return f"Library has {len(self.mechanics)} mechanics: {', '.join(names)}"

    def clear(self):
        self.mechanics = []
        self._context_use_count = {}
        if os.path.exists(self.filepath):
            os.remove(self.filepath)
        print(f"[Library] Cleared. {self.filepath} deleted.")


# ── Test ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    lib = MechanicLibrary()
    
    print("\n" + "="*70)
    print("Testing Semantic Retrieval (with query)")
    print("="*70)
    query = "I want scoring mechanics"
    results = lib.retrieve(k=4, query=query)
    print(f"\nQuery: '{query}'")
    print(f"Retrieved {len(results)} mechanics:\n")
    for i, m in enumerate(results, 1):
        print(f"{i}. {m['mechanic_name']} | Type: {m['mechanic_type']} | {m['description']}")
    
    print("\n" + "="*70)
    print("Testing Diversity Retrieval (without query)")
    print("="*70)
    lib._context_use_count = {}
    results = lib.retrieve(k=3, query=None)
    print(f"\nRetrieved {len(results)} mechanics:\n")
    for i, m in enumerate(results, 1):
        print(f"{i}. {m['mechanic_name']} | Type: {m['mechanic_type']} | {m['description']}")
    
    print("\n" + "="*70 + "\n")

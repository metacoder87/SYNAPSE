"""P0.3 — Embedding model benchmark (all-MiniLM-L6-v2).

Run ON YOUR MACHINE:
    pip install sentence-transformers
    python scripts/benchmark_embeddings.py

Pass criteria (PROJECT_PLAN.md P0.3): 100 texts embedded in < 30s on CPU.
"""

import json
import time

from sentence_transformers import SentenceTransformer

PASS_SECONDS = 30.0
N_TEXTS = 100

SAMPLE = (
    "We are seeking a Corporate AI Architect to lead macro-level strategic design "
    "of our enterprise machine learning platform. The role is 100% remote within "
    "the United States and includes comprehensive relocation assistance. "
    "Responsibilities include multi-agent orchestration, vector database design, "
    "LLMOps observability, and executive stakeholder alignment. "
) * 3  # ~150 words, roughly job-description length


def main() -> None:
    print("Loading all-MiniLM-L6-v2 (downloads ~90MB on first run)...")
    t0 = time.perf_counter()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    load_s = time.perf_counter() - t0

    texts = [f"[{i}] {SAMPLE}" for i in range(N_TEXTS)]

    # Warm up
    model.encode(texts[:5])

    t0 = time.perf_counter()
    vecs = model.encode(texts, batch_size=32, show_progress_bar=True)
    embed_s = time.perf_counter() - t0

    result = {
        "model_load_seconds": round(load_s, 2),
        "texts_embedded": N_TEXTS,
        "embed_seconds": round(embed_s, 2),
        "texts_per_second": round(N_TEXTS / embed_s, 1),
        "vector_dim": int(vecs.shape[1]),
        "pass": embed_s < PASS_SECONDS,
    }

    try:
        with open("benchmark_results.json") as f:
            existing = json.load(f)
    except FileNotFoundError:
        existing = {}
    existing["embeddings"] = result
    with open("benchmark_results.json", "w") as f:
        json.dump(existing, f, indent=2)

    print(json.dumps(result, indent=2))
    print(f"\n=== VERDICT: {'PASS' if result['pass'] else 'FAIL'} "
          f"({result['embed_seconds']}s for {N_TEXTS} texts, threshold {PASS_SECONDS}s) ===")


if __name__ == "__main__":
    main()

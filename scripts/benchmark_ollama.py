"""P0.1/P0.2 — Ollama generation benchmark.

Run ON YOUR MACHINE (needs Ollama running locally):
    ollama pull llama3:8b && ollama pull mistral:7b
    python scripts/benchmark_ollama.py

Pass criteria (PROJECT_PLAN.md P0.2): >= 10 tokens/sec sustained.
Uses only the standard library — no pip installs needed.
"""

import json
import time
import urllib.request

OLLAMA_URL = "http://localhost:11434"
MODELS = ["llama3:8b", "mistral:7b"]
TARGET_TOKENS = 500
PASS_TOK_PER_SEC = 10.0

PROMPT = (
    "Write a detailed markdown research dossier (about 500 words) on a fictional "
    "company called NeoGrid Systems that is hiring a Corporate AI Architect. "
    "Include sections with headers, a bullet list of interview talking points, "
    "and a markdown table comparing three of its products."
)


def bench(model: str) -> dict:
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps(
            {
                "model": model,
                "prompt": PROMPT,
                "stream": False,
                "options": {"num_predict": TARGET_TOKENS},
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    wall = time.perf_counter() - start

    eval_count = data.get("eval_count", 0)
    eval_ns = data.get("eval_duration", 1)
    tok_per_sec = eval_count / (eval_ns / 1e9)
    load_s = data.get("load_duration", 0) / 1e9

    return {
        "model": model,
        "tokens_generated": eval_count,
        "generation_tok_per_sec": round(tok_per_sec, 2),
        "model_load_seconds": round(load_s, 2),
        "total_wall_seconds": round(wall, 2),
        "pass": tok_per_sec >= PASS_TOK_PER_SEC,
    }


def main() -> None:
    results = []
    for model in MODELS:
        print(f"\n--- Benchmarking {model} (first run includes model load) ---")
        try:
            # Run twice: first warms the model into RAM, second measures steady state
            bench(model)
            r = bench(model)
        except Exception as e:  # noqa: BLE001
            r = {"model": model, "error": str(e), "pass": False}
        results.append(r)
        print(json.dumps(r, indent=2))

    with open("benchmark_results.json", "w") as f:
        json.dump({"ollama": results}, f, indent=2)

    print("\n=== VERDICT ===")
    for r in results:
        status = "PASS" if r.get("pass") else "FAIL"
        rate = r.get("generation_tok_per_sec", "n/a")
        print(f"  {r['model']}: {status} ({rate} tok/s, threshold {PASS_TOK_PER_SEC})")
    print("\nWatch Task Manager during the run: if RAM is swapping to disk, "
          "consider a quantized variant (e.g. llama3:8b-instruct-q4_0).")


if __name__ == "__main__":
    main()

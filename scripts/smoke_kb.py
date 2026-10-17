"""Smoke test for Phase 1: ingest sample docs, run two searches, ping the LLM once.

Run from the project root:  python scripts/smoke_kb.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from agent.llm import get_llm, model_name, model_notice, provider  # noqa: E402
from kb import store  # noqa: E402

print("== Ingest sample_docs ==")
for r in store.ingest_folder(ROOT / "sample_docs"):
    print(f"  {r['source']:<28} {r['status']:<28} chunks={r['chunks']}")

print("\n== Documents ==")
for d in store.list_documents():
    print(f"  {d['source']:<28} {d['chunks']} chunks")

for q in ["What does corrective RAG do when retrieval fails?", "What are MCP resources?"]:
    print(f"\n== Search: {q} ==")
    for hit in store.search(q, k=3):
        snippet = hit["text"][:90].replace("\n", " ")
        print(f"  [{hit['source']} p.{hit['page']}] d={hit['distance']}  {snippet}...")

print(f"\n== LLM ping ({provider()} / {model_name('fast')}) ==")
if model_notice():
    print("  note:", model_notice())
reply = get_llm("fast").invoke("Reply with exactly one word: ready")
print("  LLM says:", reply.content.strip())
print("\nSmoke KB: OK")

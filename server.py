"""StudyPilot web API (Starlette + uvicorn) – the backend for the React + Vite frontend.

Run:  python server.py   →  http://localhost:8000
  * If frontend/dist exists (npm run build), the React app is served from the same port.
  * During frontend development, `npm run dev` (port 5173) proxies /api/* to this server.

Long-running actions (chat, study pack, inbox) stream NDJSON: one JSON event per line,
so the UI can show agent / workflow steps live.
"""
import base64
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from agent import llm
from agent.graph import get_graph, get_graph_mermaid, stream_agent
from agent.tools import NOTES_DIR
from automation.study_pack import INBOX, process_inbox, read_runs, run_study_pack
from kb import store

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "frontend" / "dist"


# ---------- helpers ----------

def ndjson(job) -> StreamingResponse:
    """Run job(emit) in a worker thread and stream every emitted event as one JSON line."""
    events: queue.Queue = queue.Queue()

    def worker():
        try:
            job(events.put)
        except Exception as e:  # turn API errors into a friendly message for the UI
            events.put({"type": "error", "error": llm.friendly_error(e)})
        finally:
            events.put(None)  # end of stream

    threading.Thread(target=worker, daemon=True).start()

    def lines():
        while (event := events.get()) is not None:
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")


async def body_json(request: Request) -> dict:
    try:
        return await request.json()
    except Exception:
        return {}


# ---------- status ----------

async def status(request: Request):
    def info():
        return {"provider": llm.provider(), "main_model": llm.model_name("main"),
                "fast_model": llm.model_name("fast"), "has_key": llm.has_api_key(),
                "substitutions": llm.model_substitutions(), "kb": store.stats()}
    return JSONResponse(await run_in_threadpool(info))


# ---------- agent chat ----------

async def chat(request: Request):
    body = await body_json(request)
    question = str(body.get("question", ""))
    thread_id = str(body.get("thread_id") or "web")

    def job(emit):
        for event in stream_agent(question, thread_id):
            emit(event)
    return ndjson(job)


# ---------- knowledge base ----------

async def list_docs(request: Request):
    return JSONResponse(await run_in_threadpool(store.list_documents))


async def upload_docs(request: Request):
    """Save uploaded PDF/TXT/MD files into inbox/ and ingest them."""
    form = await request.form()
    results = []
    for upload in form.getlist("files"):
        name = Path(upload.filename or "").name  # strip any folder parts from the client
        if Path(name).suffix.lower() not in store.SUPPORTED:
            results.append({"source": name, "status": "unsupported file type", "chunks": 0})
            continue
        INBOX.mkdir(exist_ok=True)
        path = INBOX / name
        path.write_bytes(await upload.read())
        results.append(await run_in_threadpool(store.ingest_file, path))
    return JSONResponse({"results": results})


async def load_samples(request: Request):
    return JSONResponse({"results": await run_in_threadpool(store.ingest_folder, ROOT / "sample_docs")})


async def delete_doc(request: Request):
    name = request.path_params["name"]
    return JSONResponse({"deleted": name, "chunks": await run_in_threadpool(store.delete_document, name)})


async def search(request: Request):
    q = request.query_params.get("q", "")
    k = max(1, min(int(request.query_params.get("k", 4)), 10))
    return JSONResponse(await run_in_threadpool(store.search, q, k))


async def notes(request: Request):
    files = sorted(NOTES_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return JSONResponse([{"name": p.name, "content": p.read_text(encoding="utf-8")} for p in files])


# ---------- automation ----------

async def study_pack(request: Request):
    doc = str((await body_json(request)).get("doc", ""))

    def job(emit):
        result = run_study_pack(doc, on_step=lambda step, s: emit({"type": "step", "step": step, "status": s}))
        emit({"type": "result", **result})
    return ndjson(job)


async def inbox_pending(request: Request):
    INBOX.mkdir(exist_ok=True)
    return JSONResponse([p.name for p in sorted(INBOX.iterdir())
                         if p.is_file() and p.suffix.lower() in store.SUPPORTED])


async def inbox_process(request: Request):
    def job(emit):
        results = process_inbox(on_step=lambda step, s: emit({"type": "step", "step": step, "status": s}))
        emit({"type": "result", "results": results})
    return ndjson(job)


async def runs(request: Request):
    return JSONResponse(list(reversed(read_runs())))


# ---------- graph ----------

_graph_cache: dict = {}


async def graph(request: Request):
    """{png: base64 | null, mermaid: str}. PNG is rendered once via mermaid.ink (needs internet)."""
    if not _graph_cache:
        def render():
            mermaid = get_graph_mermaid()
            try:
                png = base64.b64encode(get_graph().get_graph().draw_mermaid_png()).decode()
            except Exception:
                png = None
            return {"png": png, "mermaid": mermaid}
        _graph_cache.update(await run_in_threadpool(render))
    return JSONResponse(_graph_cache)


# ---------- MCP ----------

async def mcp_demo(request: Request):
    """Run mcp_client_demo.py, which launches mcp_server.py over stdio and calls its tools."""
    def run():
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.run([sys.executable, str(ROOT / "mcp_client_demo.py")], cwd=ROOT, env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=240)
        output = proc.stdout
        if proc.returncode != 0:
            output += "\n[stderr]\n" + proc.stderr[-1500:]
        return {"ok": proc.returncode == 0, "output": output}
    return JSONResponse(await run_in_threadpool(run))


async def mcp_config(request: Request):
    return JSONResponse({"mcpServers": {"studypilot": {
        "command": str(ROOT / ".venv" / "Scripts" / "python.exe"),
        "args": [str(ROOT / "mcp_server.py")]}}})


# ---------- app ----------

async def on_error(request: Request, exc: Exception):
    return JSONResponse({"error": llm.friendly_error(exc)}, status_code=500)


routes = [
    Route("/api/status", status),
    Route("/api/chat", chat, methods=["POST"]),
    Route("/api/documents", list_docs),
    Route("/api/documents", upload_docs, methods=["POST"]),
    Route("/api/documents/samples", load_samples, methods=["POST"]),
    Route("/api/documents/{name:path}", delete_doc, methods=["DELETE"]),
    Route("/api/search", search),
    Route("/api/notes", notes),
    Route("/api/study-pack", study_pack, methods=["POST"]),
    Route("/api/inbox", inbox_pending),
    Route("/api/inbox/process", inbox_process, methods=["POST"]),
    Route("/api/runs", runs),
    Route("/api/graph", graph),
    Route("/api/mcp-demo", mcp_demo, methods=["POST"]),
    Route("/api/mcp-config", mcp_config),
]
if DIST.exists():  # serve the built React app on the same port
    routes.append(Mount("/", StaticFiles(directory=DIST, html=True)))

app = Starlette(routes=routes, exception_handlers={Exception: on_error})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    port = int(os.getenv("PORT", "8000"))
    if DIST.exists():
        print(f"StudyPilot 🧭  UI + API on http://localhost:{port}")
    else:
        print(f"StudyPilot API on http://localhost:{port}  (no frontend/dist yet – run "
              "`npm run build` in frontend/, or `npm run dev` and open http://localhost:5173)")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

"""StudyPilot MCP server (stdio). Exposes the knowledge base, agent and automation
to any MCP host – Claude Desktop, an IDE, or mcp_client_demo.py.

Run directly:  python mcp_server.py   (it then waits for a client on stdin/stdout)
"""
import contextlib
import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # Claude Desktop may start us from another folder; .env and chroma_db live here

# mcp 2.x renamed FastMCP to MCPServer (same decorator API); fall back for mcp 1.x installs.
try:
    from mcp.server.mcpserver import MCPServer as FastMCP  # noqa: E402
except ImportError:
    from mcp.server.fastmcp import FastMCP  # noqa: E402

from agent.graph import run_agent  # noqa: E402
from agent.tools import NOTES_DIR, write_note  # noqa: E402
from automation.study_pack import run_study_pack  # noqa: E402
from kb import store  # noqa: E402

mcp = FastMCP("studypilot", log_level="WARNING",  # keep stderr quiet (no per-request HTTP logs)
              instructions="StudyPilot: search study notes, ask the agentic-RAG agent, "
                           "save notes and generate study packs.")


def _quiet(fn, *args, **kwargs):
    """stdout is the MCP channel – swallow any stray prints from libraries."""
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


@mcp.tool()
def search_knowledge_base(query: str, k: int = 4) -> str:
    """Semantic search over the StudyPilot knowledge base. Returns the top-k chunks with source, page and distance."""
    hits = _quiet(store.search, query, k=k)
    if not hits:
        return "No results (knowledge base empty or nothing matched)."
    return "\n\n".join(f"[{h['source']} p.{h['page']}] (distance {h['distance']})\n{h['text']}" for h in hits)


@mcp.tool()
def list_documents() -> str:
    """List every document in the knowledge base with its chunk count."""
    docs = _quiet(store.list_documents)
    return "\n".join(f"- {d['source']}: {d['chunks']} chunks" for d in docs) or "Knowledge base is empty."


@mcp.tool()
def ask_agent(question: str) -> str:
    """Ask StudyPilot's full agentic-RAG graph (router → retrieval/grading → generation → self-check, or tools).
    Returns the answer, its sources and the route taken."""
    result = _quiet(run_agent, question, thread_id="mcp")
    sources = ", ".join(result["sources"]) or "none"
    return f"{result['answer']}\n\nSources: {sources}\nRoute: {result['route']}"


@mcp.tool()
def save_note(title: str, content: str) -> str:
    """Save a markdown study note into StudyPilot's notes/ folder."""
    path = write_note(title, content)
    return f"Saved notes/{path.name}"


@mcp.tool()
def make_study_pack(doc_name: str) -> str:
    """Run the Study Pack automation (summary, 5 key terms, 5 MCQs) for a document in the knowledge base
    and return the generated markdown."""
    result = _quiet(run_study_pack, doc_name)
    if result["status"] != "success":
        return f"Study pack failed: {result.get('error')}"
    return result["markdown"]


@mcp.resource("notes://list")
def notes_list() -> str:
    """Names of all saved study notes."""
    notes = sorted(p.name for p in NOTES_DIR.glob("*.md"))
    return "\n".join(notes) or "(no notes yet)"


if __name__ == "__main__":
    mcp.run()  # stdio transport by default

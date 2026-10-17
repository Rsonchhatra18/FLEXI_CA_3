"""The agent's tools ("action groups"). Each @tool docstring is what the LLM reads
to decide when to call it, so the descriptions are written for the model.
"""
import ast
import operator
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import httpx
from langchain_core.tools import tool

from kb import store

ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = ROOT / "notes"
# Wikimedia's User-Agent policy requires a contact URL, otherwise the API answers 403.
WIKI_HEADERS = {"User-Agent": "StudyPilot/1.0 (https://github.com/Rsonchhatra18/FLEXI_CA_3; student project) httpx"}

# ---------- safe calculator (ast, never eval) ----------

_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval_node(node):
    """Recursively evaluate a whitelisted arithmetic AST."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left, right = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("exponent too large")
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"unsupported syntax: {type(node).__name__}")


def safe_calculate(expression: str) -> float:
    expr = expression.replace("^", "**").replace("×", "*").replace("÷", "/")
    # "17% of 2450" -> "(17/100)*2450"
    expr = re.sub(r"(\d+(?:\.\d+)?)\s*%\s*of\s*", r"(\1/100)*", expr, flags=re.I)
    result = _eval_node(ast.parse(expr, mode="eval"))
    if isinstance(result, float) and result.is_integer():
        return int(result)
    return round(result, 10) if isinstance(result, float) else result


@tool
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression exactly. Use this for ANY maths instead of
    calculating yourself. Supports + - * / // % ** ^ and parentheses,
    e.g. '0.17*2450 + 3**4' or '17% of 2450 + 3^4'."""
    try:
        return f"{expression} = {safe_calculate(expression)}"
    except Exception as e:  # ZeroDivisionError, SyntaxError, ValueError...
        return f"Could not evaluate '{expression}': {e}"


@tool
def current_datetime() -> str:
    """Return the current local date, day of the week and time."""
    return datetime.now().strftime("%A, %d %B %Y, %H:%M")


# ---------- Wikipedia ----------

def _wiki_summary(title: str) -> dict | None:
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(title.replace(" ", "_"))
    r = httpx.get(url, headers=WIKI_HEADERS, timeout=5, follow_redirects=True)
    if r.status_code == 404:
        return None
    r.raise_for_status()  # 403 / 5xx are real errors, not "article missing"
    return r.json() if r.json().get("extract") else None


def _wiki_search_title(topic: str) -> str | None:
    """Use Wikipedia's search to find the best page title for a loose topic."""
    r = httpx.get("https://en.wikipedia.org/w/api.php",
                  params={"action": "opensearch", "search": topic, "limit": 1, "format": "json"},
                  headers=WIKI_HEADERS, timeout=5)
    titles = r.json()[1] if r.status_code == 200 else []
    return titles[0] if titles else None


@tool
def wikipedia_lookup(topic: str) -> str:
    """Look up a general-knowledge topic (person, company, place, event, concept) on
    Wikipedia and return its summary. Pass a short topic name like 'Infosys'."""
    try:
        data = _wiki_summary(topic)
        if data is None:
            title = _wiki_search_title(topic)
            data = _wiki_summary(title) if title else None
        if data is None:
            return f"No Wikipedia article found for '{topic}'."
        page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
        return f"Wikipedia – {data.get('title')}:\n{data['extract']}\nURL: {page_url}"
    except httpx.TimeoutException:
        return "Wikipedia did not respond within 5 seconds. Try again later."
    except httpx.HTTPStatusError as e:
        return f"Wikipedia lookup failed (HTTP {e.response.status_code})."
    except Exception as e:
        return f"Wikipedia lookup failed: {type(e).__name__}"


# ---------- knowledge base & notes ----------

@tool
def search_knowledge_base(query: str) -> str:
    """Search the user's uploaded study documents (agents, RAG, MCP notes, PDFs...)
    and return the most relevant passages with their source and page."""
    hits = store.search(query, k=4)
    if not hits:
        return "The knowledge base is empty or nothing matched."
    return "\n\n".join(f"[{h['source']} p.{h['page']}] {h['text']}" for h in hits)


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60] or "note"


def write_note(title: str, content: str) -> Path:
    """Plain function (also used by the MCP server) that saves notes/<slug>.md."""
    NOTES_DIR.mkdir(exist_ok=True)
    path = NOTES_DIR / f"{slugify(title)}.md"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    path.write_text(f"# {title}\n\n{content.strip()}\n\n_Saved by StudyPilot on {stamp}_\n", encoding="utf-8")
    return path


@tool
def save_note(title: str, content: str) -> str:
    """Save a markdown study note to the notes/ folder. `content` should be the full
    note text (e.g. bullet points). Returns the saved file path."""
    path = write_note(title, content)
    return f"Saved note '{title}' to notes/{path.name}"


@tool
def list_documents() -> str:
    """List the documents currently stored in the knowledge base with chunk counts."""
    docs = store.list_documents()
    if not docs:
        return "The knowledge base is empty."
    return "\n".join(f"- {d['source']} ({d['chunks']} chunks)" for d in docs)


ALL_TOOLS = [calculator, current_datetime, wikipedia_lookup, search_knowledge_base, save_note, list_documents]

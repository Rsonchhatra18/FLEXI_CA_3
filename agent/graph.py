"""StudyPilot's brain: a LangGraph state machine combining three RAG techniques.

  guardrail ─► router ─┬─ kb ────► retrieve ─► grade_docs ─┬─► generate ─► self_check ─► END
                       │             ▲                     │        ▲            │ (unsupported, 1 retry)
                       │             └── rewrite_query ◄───┤        └────────────┘
                       │                                   └─► tools_agent   (corrective fallback)
                       ├─ tools ─► tools_agent ◄─► run_tools ─► END
                       └─ chat ──► chat ─► END

* Adaptive RAG   – the router picks kb / tools / chat per question.
* Corrective RAG – retrieved chunks are graded; bad retrieval triggers a query
                   rewrite, then a fallback to the tool agent (Wikipedia).
* Self-RAG       – the answer is checked against its context and regenerated once.
"""
import re
from typing import Annotated, TypedDict

from langchain_core.messages import (AIMessage, AnyMessage, HumanMessage,
                                     SystemMessage, ToolMessage)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agent.llm import get_llm
from agent.tools import ALL_TOOLS
from kb import store

MAX_QUESTION_CHARS = 2000
MAX_TOOL_ROUNDS = 4
HISTORY_TURNS = 3  # how many previous Q/A pairs the LLM sees

INJECTION_PATTERNS = [
    r"ignore (all |any )?(the |your )?(previous|prior|above|earlier) (instructions|prompts|rules)",
    r"disregard (all |any )?(the |your )?(previous|prior|above|system) (instructions|prompts|rules)",
    r"(reveal|show|print|repeat) (me )?(your|the) (system prompt|hidden instructions|api key)",
    r"you are now (dan|in developer mode|unrestricted)",
    r"\bjailbreak\b",
]


class AgentState(TypedDict, total=False):
    question: str
    route: str              # kb | tools | chat | blocked
    query: str              # search query (may be rewritten)
    docs: list[dict]        # retrieved / graded chunks
    answer: str
    sources: list[str]
    tool_calls: list[dict]  # [{name, args}] made this turn
    retries: int            # query rewrites done
    regenerated: bool       # self-check retry used?
    verdict: str            # self-check result
    fallback: bool          # corrective fallback to tools happened
    tool_rounds: int
    trace: list[dict]       # [{node, detail}] – reset every turn
    messages: Annotated[list[AnyMessage], add_messages]  # conversation memory


# ---------- helpers ----------

def _trace(state: AgentState, node: str, detail: str) -> list[dict]:
    return state.get("trace", []) + [{"node": node, "detail": detail}]


def _one_word(text: str, options: list[str], default: str) -> str:
    """Defensively parse a single-word LLM reply (it may add punctuation or chatter)."""
    words = re.findall(r"[a-z]+", text.lower())
    for w in words:
        if w in options:
            return w
    return default


def _history(state: AgentState) -> list[AnyMessage]:
    """Clean past dialogue (no tool chatter), excluding the current question."""
    msgs = state.get("messages", [])
    last_human = max((i for i, m in enumerate(msgs) if isinstance(m, HumanMessage)), default=0)
    clean = [m for m in msgs[:last_human]
             if isinstance(m, HumanMessage) or (isinstance(m, AIMessage) and m.content and not m.tool_calls)]
    return clean[-HISTORY_TURNS * 2:]


def _current_turn(state: AgentState) -> list[AnyMessage]:
    """Messages from the latest user question onwards (includes tool calls/results)."""
    msgs = state.get("messages", [])
    last_human = max((i for i, m in enumerate(msgs) if isinstance(m, HumanMessage)), default=0)
    return msgs[last_human:]


def _context(docs: list[dict]) -> str:
    return "\n\n".join(f"[{d['source']} p.{d['page']}]\n{d['text']}" for d in docs)


FORMAT_RULES = ("Format with Markdown. Do not use LaTeX – write maths as plain text, e.g. 0.17 × 2450 = 416.5.")


def _clean(text: str) -> str:
    """Normalise model quirks: 【source】 citations → [source]; drop stray LaTeX \\( \\) delimiters."""
    text = (text or "").strip().replace("【", "[").replace("】", "]")
    for latex, plain in (("\\(", ""), ("\\)", ""), ("\\times", "×"), ("\\cdot", "·")):
        text = text.replace(latex, plain)
    return text


# ---------- nodes ----------

def guardrail(state: AgentState) -> dict:
    """Rule-based input filter. Also resets per-turn fields (the checkpointer keeps old ones)."""
    q = (state.get("question") or "").strip()
    reset = {"question": q, "route": "", "query": q, "docs": [], "answer": "", "sources": [],
             "tool_calls": [], "retries": 0, "regenerated": False, "verdict": "",
             "fallback": False, "tool_rounds": 0, "trace": []}

    problem = None
    if not q:
        problem = "Please type a question first. 🙂"
    elif len(q) > MAX_QUESTION_CHARS:
        problem = f"That message is too long ({len(q)} chars). Please keep it under {MAX_QUESTION_CHARS}."
    elif any(re.search(p, q, re.I) for p in INJECTION_PATTERNS):
        problem = ("Sorry, I can't follow requests to override my instructions. "
                   "I'm happy to help with your study questions though!")

    if problem:
        return {**reset, "route": "blocked", "answer": problem,
                "trace": [{"node": "guardrail", "detail": "BLOCKED – " + problem}],
                "messages": [HumanMessage(q or "(empty)"), AIMessage(problem)]}
    return {**reset, "trace": [{"node": "guardrail", "detail": "passed (no injection, length ok)"}],
            "messages": [HumanMessage(q)]}


def router(state: AgentState) -> dict:
    """Adaptive RAG: a FAST model picks the strategy for this question."""
    docs = ", ".join(d["source"] for d in store.list_documents()) or "(empty)"
    prompt = (
        "Decide how to handle the user's message. Apply the FIRST rule that matches.\n"
        "1. Asks to save/write a note, list the documents, calculate something, or get the date/time → tools\n"
        "2. Mentions the user's notes, documents or study material, OR is about AI agents, agent design "
        f"patterns, RAG, MCP, LangGraph, or topics in these documents: {docs} → kb\n"
        "3. Asks a general-knowledge fact (people, companies, places, science, history) → tools\n"
        "4. Greeting, thanks, small talk, or about this conversation → chat\n\n"
        "Examples: 'What is self-RAG?' → kb | 'How does tool use work in agents?' → kb | "
        "'Summarise my notes on routing' → kb | 'What is 12*7?' → tools | 'Who is the CEO of Google?' → tools | "
        "'Save a note about RAG' → tools | 'Hello!' → chat\n\n"
        f"Message: {state['question']}\n"
        "Reply with exactly ONE word (kb, tools or chat):"
    )
    reply = get_llm("fast").invoke(prompt).content
    route = _one_word(reply, ["kb", "tools", "chat"], default="kb")
    return {"route": route, "trace": _trace(state, "router", f"route = {route} (model said: {reply.strip()[:30]!r})")}


def retrieve(state: AgentState) -> dict:
    query = state.get("query") or state["question"]
    docs = store.search(query, k=4)
    found = ", ".join(f"{d['source']} p.{d['page']} (d={d['distance']})" for d in docs) or "nothing"
    return {"docs": docs, "trace": _trace(state, "retrieve", f"query={query!r} → {found}")}


def grade_docs(state: AgentState) -> dict:
    """Corrective RAG: FAST model grades each chunk yes/no; irrelevant chunks are dropped."""
    docs = state.get("docs", [])
    if not docs:
        return {"docs": [], "trace": _trace(state, "grade_docs", "no chunks to grade")}
    prompts = [
        "Is the document chunk relevant to the question (even partially)? "
        "Reply with exactly ONE word: yes or no.\n\n"
        f"Question: {state['question']}\n\nChunk:\n{d['text']}\n\nOne word:"
        for d in docs
    ]
    replies = get_llm("fast").batch(prompts)
    kept = [d for d, r in zip(docs, replies) if _one_word(r.content, ["yes", "no"], "no") == "yes"]
    names = ", ".join(f"{d['source']} p.{d['page']}" for d in kept) or "none"
    return {"docs": kept, "trace": _trace(state, "grade_docs", f"kept {len(kept)}/{len(docs)} relevant: {names}")}


def rewrite_query(state: AgentState) -> dict:
    """Corrective RAG: turn the question into a better search query and try again."""
    prompt = ("Rewrite the question below as a short keyword search query for a vector database "
              "of study notes. Reply with ONLY the query.\n\n"
              f"Question: {state['question']}\nQuery:")
    new_q = get_llm("fast").invoke(prompt).content.strip().strip('"').splitlines()[0][:200]
    return {"query": new_q, "retries": state.get("retries", 0) + 1,
            "trace": _trace(state, "rewrite_query", f"rewritten query = {new_q!r}")}


def generate(state: AgentState) -> dict:
    """MAIN model answers strictly from the graded context, with citations."""
    strict = state.get("verdict") == "no"  # second attempt after a failed self-check
    rules = ("Answer ONLY using the context below. Cite facts with their label in square brackets exactly "
             "as given, e.g. [rag_techniques.md p.1]. If the context does not contain the answer, say so. "
             "Use short paragraphs or bullet points. " + FORMAT_RULES)
    if strict:
        rules += (" STRICT MODE: your previous answer contained unsupported claims. Use only "
                  "statements that are directly written in the context; add nothing from general knowledge.")
    msgs = [SystemMessage(f"You are StudyPilot, a helpful study assistant. {rules}\n\nContext:\n{_context(state['docs'])}"),
            *_history(state), HumanMessage(state["question"])]
    answer = _clean(get_llm("main").invoke(msgs).content)
    sources = sorted({f"{d['source']} p.{d['page']}" for d in state["docs"]})
    detail = ("STRICT regeneration" if strict else "answer drafted") + f" from {len(state['docs'])} chunks"
    return {"answer": answer, "sources": sources, "regenerated": state.get("regenerated", False) or strict,
            "trace": _trace(state, "generate", detail)}


def self_check(state: AgentState) -> dict:
    """Self-RAG: FAST model checks the answer is grounded in the context."""
    prompt = ("You are a strict fact checker. Is the ANSWER fully supported by the CONTEXT? "
              "Reply with exactly ONE word: yes or no.\n\n"
              f"CONTEXT:\n{_context(state['docs'])}\n\nANSWER:\n{state['answer']}\n\nOne word:")
    reply = get_llm("fast").invoke(prompt).content
    verdict = _one_word(reply, ["yes", "no"], default="yes")
    update = {"verdict": verdict}
    if verdict == "yes":
        update["trace"] = _trace(state, "self_check", "supported ✅ – answer is grounded in the context")
    elif not state.get("regenerated"):
        update["trace"] = _trace(state, "self_check", "NOT supported ❌ – regenerating once with a stricter prompt")
        return update  # loop back to generate; don't finalise yet
    else:
        update["answer"] = state["answer"] + "\n\n⚠ This answer may be partially unsupported by the sources."
        update["trace"] = _trace(state, "self_check", "still not supported after retry – warning appended")
    update["messages"] = [AIMessage(update.get("answer", state["answer"]))]
    return update


def chat(state: AgentState) -> dict:
    """Plain conversation – no retrieval needed (adaptive RAG skips the KB)."""
    msgs = [SystemMessage("You are StudyPilot, a friendly study assistant for AI agents, RAG and MCP "
                          "(Model Context Protocol). Keep replies short. " + FORMAT_RULES),
            *_history(state), HumanMessage(state["question"])]
    answer = _clean(get_llm("main").invoke(msgs).content)
    return {"answer": answer, "sources": [], "messages": [AIMessage(answer)],
            "trace": _trace(state, "chat", "answered directly without retrieval")}


def tools_agent(state: AgentState) -> dict:
    """ReAct-style tool agent: the LLM decides which tool to call next (max 4 rounds)."""
    rounds = state.get("tool_rounds", 0)
    docs = ", ".join(d["source"] for d in store.list_documents()) or "(none yet)"
    system = ("You are StudyPilot, a study assistant with tools. Use tools whenever they help: "
              "calculator for ANY arithmetic, wikipedia_lookup for general facts, search_knowledge_base "
              "for the user's study material, save_note to save notes, current_datetime for dates.\n"
              f"The user's study documents are: {docs}. They cover AI agents, RAG and MCP "
              "(= Model Context Protocol). When asked to write or save notes about a topic, FIRST call "
              "search_knowledge_base to gather facts, THEN call save_note with the finished note.\n"
              "If a Wikipedia summary lacks the specific detail asked for, do one more targeted lookup "
              "(e.g. a person's name). Base the final answer on tool results and keep it concise. "
              + FORMAT_RULES)
    if state.get("fallback"):
        system += (" The user's knowledge base had nothing relevant to this question, so look it up "
                   "with wikipedia_lookup and say the answer comes from Wikipedia.")
    msgs = [SystemMessage(system), *_history(state), *_current_turn(state)]

    if rounds >= MAX_TOOL_ROUNDS:  # budget used up: answer with what we have
        llm = get_llm("main")
        msgs.append(HumanMessage("Tool budget reached. Give your best final answer now."))
    else:
        llm = get_llm("main", tools=ALL_TOOLS)
    response = llm.invoke(msgs)

    if getattr(response, "tool_calls", None):
        calls = [{"name": c["name"], "args": c["args"]} for c in response.tool_calls]
        listed = "; ".join(f"{c['name']}({c['args']})" for c in calls)
        return {"messages": [response], "tool_rounds": rounds + 1,
                "tool_calls": state.get("tool_calls", []) + calls,
                "trace": _trace(state, "tools_agent", f"round {rounds + 1}: calling {listed}")}

    answer = _clean(response.content) or "I couldn't produce an answer with the available tools."
    sources = [f"tool: {c['name']}({', '.join(f'{k}={v!r}' for k, v in c['args'].items())})"
               for c in state.get("tool_calls", [])]
    return {"answer": answer, "sources": sources, "messages": [AIMessage(answer)],
            "trace": _trace(state, "tools_agent", f"final answer after {rounds} tool round(s)")}


_tool_node = ToolNode(ALL_TOOLS)


def run_tools(state: AgentState, config) -> dict:
    """Executes the tool calls with LangGraph's prebuilt ToolNode, and records them in the trace."""
    out = _tool_node.invoke(state, config)
    results = [m for m in out["messages"] if isinstance(m, ToolMessage)]
    preview = " | ".join(f"{m.name} → {str(m.content)[:80]!r}" for m in results)
    return {"messages": out["messages"], "trace": _trace(state, "run_tools", preview)}


# ---------- conditional edges ----------

def after_guardrail(state: AgentState) -> str:
    return END if state.get("route") == "blocked" else "router"


def after_router(state: AgentState) -> str:
    return {"kb": "retrieve", "tools": "tools_agent", "chat": "chat"}.get(state["route"], "retrieve")


def after_grading(state: AgentState) -> str:
    if state.get("docs"):
        return "generate"
    if state.get("retries", 0) < 1:
        return "rewrite_query"
    return "web_fallback"


def web_fallback(state: AgentState) -> dict:
    """Corrective RAG: nothing relevant in the KB even after rewriting → hand over to tools."""
    return {"fallback": True,
            "trace": _trace(state, "web_fallback", "KB had no relevant chunks after rewrite → using Wikipedia tools")}


def after_self_check(state: AgentState) -> str:
    if state.get("verdict") == "no" and not state.get("regenerated"):
        return "generate"
    return END


def after_tools_agent(state: AgentState) -> str:
    last = state["messages"][-1]
    return "run_tools" if isinstance(last, AIMessage) and last.tool_calls else END


# ---------- build ----------

def build_graph(checkpointer=None):
    g = StateGraph(AgentState)
    for name, fn in [("guardrail", guardrail), ("router", router), ("retrieve", retrieve),
                     ("grade_docs", grade_docs), ("rewrite_query", rewrite_query),
                     ("web_fallback", web_fallback), ("generate", generate),
                     ("self_check", self_check), ("chat", chat),
                     ("tools_agent", tools_agent), ("run_tools", run_tools)]:
        g.add_node(name, fn)

    g.add_edge(START, "guardrail")
    g.add_conditional_edges("guardrail", after_guardrail, ["router", END])
    g.add_conditional_edges("router", after_router, ["retrieve", "tools_agent", "chat"])
    g.add_edge("retrieve", "grade_docs")
    g.add_conditional_edges("grade_docs", after_grading, ["generate", "rewrite_query", "web_fallback"])
    g.add_edge("rewrite_query", "retrieve")
    g.add_edge("web_fallback", "tools_agent")
    g.add_edge("generate", "self_check")
    g.add_conditional_edges("self_check", after_self_check, ["generate", END])
    g.add_conditional_edges("tools_agent", after_tools_agent, ["run_tools", END])
    g.add_edge("run_tools", "tools_agent")
    g.add_edge("chat", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())


_graph = None


def get_graph():
    """Compile once per process (the MemorySaver lives inside it)."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}


def _summarise(s: dict, question: str) -> dict:
    """Pick the useful bits of the final state for UIs / scripts / MCP."""
    route = "kb → wikipedia fallback" if s.get("fallback") else s.get("route", "")
    return {"question": s.get("question", question),
            "answer": s.get("answer", ""), "sources": s.get("sources", []), "trace": s.get("trace", []),
            "route": route, "query": s.get("query", ""), "tool_calls": s.get("tool_calls", []),
            "verdict": s.get("verdict", ""), "docs": s.get("docs", [])}


def run_agent(question: str, thread_id: str = "default", graph=None) -> dict:
    """Run one turn of the conversation and return the result in one go."""
    graph = graph or get_graph()
    return _summarise(graph.invoke({"question": question}, _config(thread_id)), question)


def stream_agent(question: str, thread_id: str = "default", graph=None):
    """Same as run_agent, but yields each trace step as soon as its node finishes
    ({"type": "step", node, detail}), then {"type": "result", **result}. Used by the web UI."""
    graph = graph or get_graph()
    config = _config(thread_id)
    for update in graph.stream({"question": question}, config, stream_mode="updates"):
        for node, changes in update.items():
            trace = (changes or {}).get("trace") or []
            if trace:
                yield {"type": "step", **trace[-1]}
    yield {"type": "result", **_summarise(graph.get_state(config).values, question)}


def get_graph_mermaid() -> str:
    return get_graph().get_graph().draw_mermaid()


def get_graph_png() -> bytes | str:
    """PNG bytes of the graph (rendered via mermaid.ink); falls back to Mermaid text if offline."""
    try:
        return get_graph().get_graph().draw_mermaid_png()
    except Exception:
        return get_graph_mermaid()

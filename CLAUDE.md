# CLAUDE.md – StudyPilot (Flexi Credit CA-3)

Student: Raghav Sonchhatra, B.Tech, Symbiosis Institute of Technology, Pune. (PRN and other report details: report/student.json – git-ignored, keep the PRN out of committed files.)

> **Implementation notes (discovered while building, Oct 2026):**
> - Groq has retired `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`. Defaults are now MAIN=`openai/gpt-oss-120b`, FAST=`openai/gpt-oss-20b` (reasoning_effort=low). `agent/llm.py` auto-substitutes these if the models named in .env are unavailable, so .env never needs to be edited by the agent.
> - Installed `mcp` is 2.x: `FastMCP` was renamed to `MCPServer` (`from mcp.server.mcpserver import MCPServer`); client result fields are snake_case (`server_info`).
> - Python is 3.13 (only version installed); all deps work on it.
> - **Frontend changed at the user's request (2026-10-17): React + Vite instead of Streamlit.** `frontend/` holds the Vite app (React 19, react-markdown); `server.py` is a Starlette + uvicorn JSON API (both already installed as mcp deps) that also serves `frontend/dist`. Streamlit and its exclusive deps were uninstalled; `app.py` was deleted. Run: `cd frontend; npm install; npm run build` once, then `python server.py` → http://localhost:8000 (dev: `npm run dev` on :5173 proxies /api). Tabs have URL hashes (#chat #kb #automation #graph #mcp #courses).

You are building my college project (submission tomorrow). Work through ALL phases below in order, running and fixing each before moving on. Only stop where I say STOP.

=== PROJECT BRIEF ===
**StudyPilot – an Agentic RAG study assistant with tools, an automation workflow and an MCP server.** It must demonstrate learnings from 4 courses:
(1) Agentic AI for Beginners – agents, tools/actions, knowledge bases
(2) AI Agents & AI Automation – automated multi-step workflows
(3) AI Engineer Agentic Track: Agent & MCP – agent design patterns, evaluator/reflection, MCP
(4) Private Agentic RAG with LangGraph & Ollama – LangGraph state machines, ChromaDB, corrective/self-RAG, local LLM option

Project folder: C:\Users\ASUS\Desktop\COLLEGE\Projects\FLEXI_CA_3 (current directory). GitHub remote: https://github.com/Rsonchhatra18/FLEXI_CA_3.git (public, currently empty).

STRICT constraints:
- Windows 11 + PowerShell. venv at .venv, always `pip install --no-cache-dir`.
- Very low disk space. ONLY these Python deps: langgraph, langchain-openai, chromadb, pypdf, mcp, python-dotenv, python-docx (+ starlette/uvicorn, already pulled in by mcp). Frontend: React + Vite (npm). NO torch, transformers, sentence-transformers, docling, crewai, autogen, Docker.
- SECRETS: .env already exists with my GROQ_API_KEY. Never overwrite it, never print or echo the key, never copy it into any other file (code, README, CLAUDE.md, report). Keep .env in .gitignore. Load it only via python-dotenv.
- LLM via ChatOpenAI(base_url=...). Default provider Groq: base_url https://api.groq.com/openai/v1, MAIN_MODEL=llama-3.3-70b-versatile (final answers), FAST_MODEL=llama-3.1-8b-instant (routing/grading). Optional PROVIDER=ollama → http://localhost:11434/v1, OLLAMA_MODEL=qwen2.5:1.5b. If MAIN_MODEL is rate-limited, fall back to FAST_MODEL.
- Embeddings: ChromaDB's built-in default embedding function, persisted to ./chroma_db.
- Simple, readable, commented code in small files. No test frameworks, just smoke scripts.
- Save this whole prompt as CLAUDE.md first so context survives restarts.

=== PHASE 1 – setup + knowledge base ===
1. Create venv, requirements.txt, .env.example (placeholder values only), extend the existing .gitignore if needed. Install deps.
2. Structure: server.py + frontend/ (React + Vite; originally app.py), agent/{llm.py,tools.py,graph.py}, kb/store.py, automation/study_pack.py, mcp_server.py, mcp_client_demo.py, scripts/, sample_docs/, notes/, outputs/, inbox/, report/screenshots/
3. agent/llm.py: get_llm(kind="main"|"fast") reading .env.
4. kb/store.py: ingest_file(path) for PDF/TXT/MD (pypdf, keep page numbers), ~800-char chunks with 150 overlap, metadata {source, page}, skip already-ingested files via hash; ingest_folder(); search(query,k=4) → text+metadata+distance; list_documents() with chunk counts; delete_document(name).
5. Write 3 one-page sample docs in sample_docs/ in your own words: agent_design_patterns.md (prompt chaining, routing, tool use, evaluator-optimizer, orchestrator-workers), rag_techniques.md (naive, corrective, self-RAG, adaptive RAG), mcp_basics.md (hosts/clients/servers, tools/resources/prompts).
6. scripts/smoke_kb.py: ingest sample_docs, run 2 searches, plus one tiny LLM call to verify the key works. Run it and fix errors.

=== PHASE 2 – LangGraph agent + tools ===
agent/tools.py – LangChain @tool functions (the agent's "action groups"): calculator(expression) using ast (no eval); current_datetime(); wikipedia_lookup(topic) via Wikipedia REST summary API with httpx, 5s timeout, graceful errors; search_knowledge_base(query); save_note(title, content) → notes/<slug>.md; list_documents().

agent/graph.py – LangGraph v1 StateGraph implementing adaptive + corrective + self-RAG.
State: question, route, query, docs, answer, sources, tool_calls, retries, trace (list of {node, detail}), messages.
Flow:
- guardrail (rule-based): empty / too long / prompt-injection ("ignore previous instructions" etc.) → polite refusal → END
- router (FAST) → kb | tools | chat
- kb: retrieve (k=4) → grade_docs (FAST, yes/no per chunk) → relevant → generate; none and retries<1 → rewrite_query → retrieve; still none → tools_agent (corrective fallback to Wikipedia)
- generate (MAIN): answer only from context, cite as [source p.N] → self_check (FAST: "is the answer supported by the context? yes/no"); if no and not retried → regenerate once with a stricter prompt, else append "⚠ may be partially unsupported" → END
- tools: tools_agent = LLM bound to tools + ToolNode loop, max 4 rounds → END
- chat: generate directly → END
Every node appends to trace. MemorySaver checkpointer with thread_id for multi-turn chat. Grading/routing prompts must ask for a single word and parse defensively.
Expose build_graph(), run_agent(question, thread_id) → {answer, sources, trace, route}, get_graph_png() using draw_mermaid_png with fallback to draw_mermaid() text.
scripts/smoke_agent.py – print route + trace + answer for: "What is corrective RAG?", "Explain the evaluator-optimizer pattern", "What is 17% of 2450 plus 3^4?", "Who founded Infosys?", "Save a note titled MCP summary with 3 bullet points about MCP". Fix until all 5 work.

=== PHASE 3 – automation workflow + MCP ===
automation/study_pack.py – deterministic multi-step workflow (like an n8n flow: trigger → steps → output):
- run_study_pack(doc_name, on_step=None): load doc chunks from Chroma (truncate ~6000 chars) → summary (MAIN) → 5 key terms with definitions → 5 MCQs with answers → save outputs/<doc>_study_pack.md → append {timestamp, doc, status, seconds, output} to outputs/runs.jsonl. Call on_step(step_name, status) after each step.
- process_inbox(): ingest new files in inbox/ and run a study pack for each (the "trigger").
- CLI: python -m automation.study_pack --doc <name> | --inbox
mcp_server.py – official `mcp` Python SDK (FastMCP), stdio, name "studypilot". Check the installed version's API first. Tools: search_knowledge_base(query,k=4), list_documents(), ask_agent(question) (runs the full graph, returns answer + sources), save_note(title, content), make_study_pack(doc_name). Resource: notes://list.
mcp_client_demo.py – start mcp_server.py over stdio using sys.executable, list tools, call list_documents, search_knowledge_base("self-RAG"), ask_agent("What is MCP?"), print clean labelled sections.
Run the CLI workflow and the MCP demo; fix errors.

=== PHASE 4 – Web UI: React + Vite frontend (frontend/) + Starlette API (server.py) ===
(Originally Streamlit app.py – replaced by React + Vite at the user's request.)
Presentable, it will be screenshotted.
- Wide layout, title "StudyPilot 🧭" + tagline. Sidebar: provider/model in use, KB stats, "New chat" button, footer listing the 4 courses.
- Tabs:
  1. 💬 Agent Chat – chat history; each answer shows a route badge, sources, and an expander "🔍 Agent trace" (nodes visited, docs kept, rewritten query, tools called with args, self-check verdict). 3 example-question buttons.
  2. 📚 Knowledge Base – upload PDF/TXT/MD (save to inbox/, ingest), "Load sample docs" button, documents table with chunk counts, delete, quick search with top chunks + distance.
  3. ⚙️ Automation – pick a doc → "Run Study Pack" with a live status box showing steps, render markdown + download button; "Process inbox" button; run history table from runs.jsonl.
  4. 🕸️ Agent Graph – graph PNG (fallback: mermaid code) + one line per node naming the RAG technique it implements.
  5. 🔌 MCP – table of exposed tools, button that runs mcp_client_demo.py via subprocess and shows its output, plus Claude Desktop config JSON.
  6. 🎓 Course Mapping – table: Course → concept learned → where it's used in StudyPilot.
- Compile the graph once per server process. Friendly messages for missing key / rate limits instead of tracebacks. Chat / study pack / inbox stream NDJSON so steps show live.
Build the frontend and start `python server.py`; make sure it boots without errors.

>>> STOP HERE. Tell me what to click in each tab, and remind me to save these screenshots into report/screenshots/:
c1.png–c4.png (my 4 course progress screenshots: c1 Agentic AI for Beginners, c2 AI Agents & AI Automation, c3 AI Engineer Agentic Track, c4 Private Agentic RAG),
p01_chat_answer.png, p02_agent_trace.png, p03_tool_answer.png, p04_knowledge_base.png, p05_automation.png, p06_agent_graph.png, p07_mcp_demo.png, p08_course_mapping.png.
Wait until I reply "screenshots done", then continue with Phase 5.

=== PHASE 5 – README, GitHub, report ===
1. README.md: summary, features, architecture (mermaid of the graph), course→feature table, tech stack, Windows setup (venv, copy .env.example to .env, run), running automation + MCP demo + Claude Desktop config, screenshots section (p01–p08), future scope.
2. Git: run `git remote -v`. If this folder isn't a repo yet, `git init`, then set origin to https://github.com/Rsonchhatra18/FLEXI_CA_3.git and use branch main. BEFORE the first commit run `git status` and confirm .env, .venv and chroma_db are NOT staged, and grep the staged files for "gsk_" to make sure no key leaked. Make a few meaningful commits and `git push -u origin main` (I'll complete the browser login if Git asks). Then remind me to screenshot the repo page as report/screenshots/p09_github.png.
3. report/make_report.py (python-docx) → report/CA3_Report_StudyPilot.docx:
   - Title page: "Flexi Credit Course – CA-3: Agentic AI Learning & Implementation Project", Name + PRN (from report/student.json), B.Tech, Symbiosis Institute of Technology, Pune, today's date.
   - 1 Introduction & objective
   - 2 Courses & progress table (Course | Platform: Infosys Springboard (Udemy) | Duration | Level | Status | Approx. progress | Link):
     Agentic AI for Beginners | 5h 51m | Beginner | Open | ~80% | https://infyspringboard.onwingspan.com/web/en/app/toc/lex_auth_01458327122046976031433/overview
     AI Agents & AI Automation — The Practical Agentic AI Guide | 8h 12m | Beginner | Open | ~75% | https://infyspringboard.onwingspan.com/web/en/app/toc/lex_auth_01454950814459494445608/overview
     AI Engineer Agentic Track: The Complete Agent & MCP Course | 17h 3m | Intermediate | Started | ~60% | https://infyspringboard.onwingspan.com/web/en/app/toc/lex_auth_01458326782454169631411/overview
     Agentic AI – Private Agentic RAG with LangGraph and Ollama | 17h 37m | Advanced | Open | ~50% | https://infyspringboard.onwingspan.com/web/en/app/toc/lex_auth_01458327505077862431430/overview
     followed by screenshots c1–c4 with captions.
   - 3 Key learnings per course (4–5 bullets each)
   - 4 Project: problem statement, features, tech stack, architecture (insert graph PNG), course→feature mapping table
   - 5 Implementation summary per module
   - 6 Results: p01–p09 with captions (skip missing files with a note)
   - 7 GitHub repository: https://github.com/Rsonchhatra18/FLEXI_CA_3 (clickable)
   - 8 Conclusion & future scope
   Formatting: headings, page breaks between major sections, images 6" wide, shaded table headers, page numbers in footer.
Generate it, and tell me to rerun `python report/make_report.py` after adding p09_github.png. Finally list what I still need to fill in (name/PRN – now provided above).

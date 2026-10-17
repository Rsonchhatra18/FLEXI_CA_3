// Static content shared by several tabs.

export const COURSES = [
  { short: 'Agentic AI for Beginners', full: 'Agentic AI for Beginners',
    duration: '5h 51m', level: 'Beginner', focus: 'Agents, tools / actions, knowledge bases' },
  { short: 'AI Agents & AI Automation', full: 'AI Agents & AI Automation — The Practical Agentic AI Guide',
    duration: '8h 12m', level: 'Beginner', focus: 'Automated multi-step workflows' },
  { short: 'AI Engineer Agentic Track: Agent & MCP', full: 'AI Engineer Agentic Track: The Complete Agent & MCP Course',
    duration: '17h 3m', level: 'Intermediate', focus: 'Design patterns, evaluator / reflection, MCP' },
  { short: 'Private Agentic RAG with LangGraph & Ollama', full: 'Agentic AI – Private Agentic RAG with LangGraph and Ollama',
    duration: '17h 37m', level: 'Advanced', focus: 'LangGraph, ChromaDB, corrective / self-RAG, local LLMs' },
]

export const EXAMPLES = [
  'What is corrective RAG?',
  'What is 17% of 2450 plus 3^4?',
  'Who founded Infosys?',
]

// colour per route (first word of the route string)
export const ROUTE_COLOURS = {
  kb: 'var(--kb)', tools: 'var(--tools)', chat: 'var(--chat)', blocked: 'var(--blocked)',
}

export const GRAPH_NODES = [
  ['guardrail', 'Guardrail', 'Blocks empty, oversized and prompt-injection inputs before any LLM call'],
  ['router', 'Adaptive RAG', 'FAST model picks the strategy: kb / tools / chat'],
  ['retrieve', 'Retrieval', 'Top-4 chunks from ChromaDB (local ONNX embeddings)'],
  ['grade_docs', 'Corrective RAG', 'Grades every chunk yes/no and drops irrelevant ones'],
  ['rewrite_query', 'Corrective RAG', 'Rewrites the search query and retries retrieval once'],
  ['web_fallback', 'Corrective RAG', 'Falls back to Wikipedia when the KB has nothing relevant'],
  ['generate', 'Grounded generation', 'MAIN model answers only from context, citing [source p.N]'],
  ['self_check', 'Self-RAG', 'Evaluator-optimizer: regenerates once if the answer is unsupported'],
  ['tools_agent', 'Tool use / ReAct', 'LLM bound to 6 tools decides the next action (max 4 rounds)'],
  ['run_tools', 'ToolNode', "LangGraph's prebuilt ToolNode executes the tool calls"],
  ['chat', 'Direct answer', 'Small talk is answered without retrieval'],
]

export const MCP_TOOLS = [
  ['tool', 'search_knowledge_base(query, k=4)', 'Semantic search over ChromaDB'],
  ['tool', 'list_documents()', 'Documents + chunk counts'],
  ['tool', 'ask_agent(question)', 'Runs the full LangGraph agent, returns answer + sources'],
  ['tool', 'save_note(title, content)', 'Writes notes/<slug>.md'],
  ['tool', 'make_study_pack(doc_name)', 'Runs the Study Pack automation workflow'],
  ['resource', 'notes://list', 'Lists the saved study notes'],
]

export const COURSE_MAP = [
  [0, 'What an agent is; tools / action groups', 'tools_agent with 6 @tool functions (agent/tools.py)'],
  [0, 'Knowledge bases', 'ChromaDB knowledge base with upload, delete & search (kb/store.py)'],
  [1, 'Multi-step automation workflows (n8n style)', 'Study Pack workflow: trigger → steps → output (automation/study_pack.py)'],
  [1, 'Triggers & run logging', 'inbox/ trigger + outputs/runs.jsonl run history'],
  [2, 'Routing & tool-use design patterns', 'router node + ReAct tool loop (agent/graph.py)'],
  [2, 'Evaluator-optimizer / reflection', 'self_check node regenerates unsupported answers'],
  [2, 'Model Context Protocol', 'MCP server with 5 tools + 1 resource (mcp_server.py)'],
  [3, 'LangGraph state machines + memory', 'StateGraph with conditional edges, MemorySaver per thread'],
  [3, 'Corrective RAG & Self-RAG', 'grade_docs → rewrite_query → web_fallback; self_check'],
  [3, 'Private / local LLMs with Ollama', 'PROVIDER=ollama switches every call to a local model'],
]

export const WORKFLOW_STEPS = [
  ['trigger', 'Trigger'],
  ['load_document', 'Load document'],
  ['summarise', 'Summarise'],
  ['key_terms', 'Key terms'],
  ['mcqs', 'MCQs'],
  ['save_markdown', 'Save markdown'],
  ['log', 'Log run'],
]

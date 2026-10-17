# Agent Design Patterns

An AI agent is a program in which a large language model (LLM) decides what to do next instead of following a fixed script. In practice most useful systems sit somewhere between a plain "workflow" (the developer hard-codes the steps) and a fully autonomous agent (the model picks every step). Five building-block patterns show up again and again.

## 1. Prompt chaining
The task is broken into a fixed sequence of LLM calls, where the output of one call becomes the input of the next. Example: first write an outline, then expand the outline into a draft, then translate the draft. A cheap programmatic "gate" can be placed between steps to check that the intermediate output looks right before continuing. Chaining trades a little latency for much higher accuracy, because each call has a smaller, clearer job.

## 2. Routing
A first step classifies the input and sends it to a specialised handler. A customer-support bot might route refund questions, technical questions and general chat to three different prompts or even three different models. Routing keeps each downstream prompt focused, and lets you send easy questions to a small, cheap model and hard ones to a large model.

## 3. Tool use
The model is given a list of tools (functions with a name, a description and typed arguments). Instead of answering directly it can emit a structured "tool call"; the program runs the function and returns the result to the model, which then continues. Calculators, web search, database queries and file writers are typical tools. Good tool descriptions matter as much as good prompts, because the model chooses tools by reading those descriptions. The loop of reason → act → observe is often called the ReAct pattern.

## 4. Evaluator-optimizer (reflection)
One LLM call produces an answer and a second call evaluates it against clear criteria, returning feedback or a pass/fail verdict. If the answer fails, the generator tries again using the feedback. This loop mirrors how a human writer revises a draft after review. It works best when evaluation criteria are explicit, for example "is every claim supported by the provided context?". A maximum number of iterations prevents endless loops.

## 5. Orchestrator-workers
A central orchestrator LLM looks at a complex task, decides which sub-tasks are needed at run time, hands each sub-task to a worker (another LLM call or agent), and finally synthesises the workers' results. Unlike prompt chaining, the sub-tasks are not known in advance. Coding agents that must edit an unknown number of files, or research agents that search several sources, use this pattern.

## Choosing a pattern
Start with the simplest thing that works: a single well-prompted call with retrieval. Add chaining or routing when the task has clear stages or categories, add tools when the model needs fresh data or actions, and add evaluator loops when quality must be verified. Full autonomy should be reserved for open-ended problems, because every extra decision the model makes is another place it can go wrong. Always log each step (a "trace") so the agent's behaviour can be inspected and debugged.

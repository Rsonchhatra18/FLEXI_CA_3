# Retrieval-Augmented Generation (RAG) Techniques

Retrieval-Augmented Generation gives an LLM access to knowledge it was not trained on. Documents are split into chunks, each chunk is turned into an embedding vector and stored in a vector database such as ChromaDB. At question time the question is embedded too, the most similar chunks are retrieved, and they are pasted into the prompt as context. This grounds the answer in real sources, reduces hallucination and allows citations.

## 1. Naive RAG
The basic pipeline: retrieve the top-k chunks, stuff them into the prompt, generate. It is simple and fast, but it has no way to notice when retrieval fails. If the retrieved chunks are irrelevant, the model either hallucinates or gives a vague answer, and nothing checks whether the final answer actually matches the sources.

## 2. Corrective RAG (CRAG)
Corrective RAG adds a grading step between retrieval and generation. A lightweight LLM (or classifier) judges each retrieved chunk as relevant or not relevant to the question. Irrelevant chunks are thrown away. If nothing useful is left, the system takes a corrective action: it rewrites the query into a better search query and retrieves again, and if that still fails it falls back to an external source such as a web or Wikipedia search. The key idea is "don't trust retrieval blindly – verify it and fix it".

## 3. Self-RAG
Self-RAG makes the model reflect on its own output. After generating an answer, the system asks whether the answer is supported by the retrieved context (a groundedness or hallucination check) and whether it actually answers the question. If the check fails, the answer is regenerated with stricter instructions, or the user is warned that parts may be unsupported. Self-RAG is an application of the evaluator-optimizer pattern to retrieval.

## 4. Adaptive RAG
Not every question needs retrieval. Adaptive RAG puts a router in front of the pipeline that decides the best strategy for each query: answer directly for small talk, use the vector store for questions about the user's documents, or call tools for calculations and live facts. This saves time and tokens and avoids polluting simple answers with irrelevant context.

## Putting them together
A modern "agentic RAG" system combines all of these inside a state machine. LangGraph is a popular choice: each technique becomes a node (route, retrieve, grade, rewrite, generate, self-check) and conditional edges decide the path. The graph keeps a shared state (question, documents, answer, retry counters) and a checkpointer stores conversation memory per thread. Running the LLM locally with Ollama makes the whole pipeline private, because neither the documents nor the questions leave the machine.

## Practical tips
Chunk size of roughly 500–1000 characters with some overlap works well for prose. Always keep metadata such as file name and page number so answers can cite "[source p.N]". Limit retries so a bad question cannot cause an infinite loop, and log every step for debugging.

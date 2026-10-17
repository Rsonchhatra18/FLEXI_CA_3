# MCP summary

- MCP (Model Context Protocol) is an open standard (introduced by Anthropic in late 2024) that provides a uniform "USB‑C"‑like interface for AI applications to connect to external tools and data.
- Core architecture consists of **hosts** (the AI app), **clients** (connectors inside the host), and **servers** (lightweight programs exposing capabilities via JSON‑RPC 2.0 over stdio or HTTP).
- MCP separates capabilities from applications, enabling a single server (e.g., a file‑system or knowledge‑base tool) to be reused across many AI agents while improving security through host‑controlled tool approval.

_Saved by StudyPilot on 2026-10-16 23:29_

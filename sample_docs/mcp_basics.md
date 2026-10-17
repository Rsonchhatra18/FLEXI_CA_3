# Model Context Protocol (MCP) Basics

The Model Context Protocol is an open standard, introduced by Anthropic in late 2024, that defines how AI applications connect to external tools and data. Before MCP, every AI app needed its own custom integration for every service. MCP works like a "USB-C port for AI": a tool written once as an MCP server can be plugged into any MCP-compatible application.

## Architecture: hosts, clients and servers
- **Host** – the AI application the user interacts with, for example Claude Desktop, an IDE assistant, or a custom agent. The host contains the LLM and decides when to use external capabilities.
- **Client** – a connector inside the host. Each client keeps a one-to-one connection with a single server and handles the protocol messages.
- **Server** – a lightweight program that exposes capabilities (tools, resources, prompts) over MCP. A server might wrap a file system, a database, GitHub, or – in StudyPilot's case – a personal knowledge base.

Messages use JSON-RPC 2.0. The two common transports are **stdio**, where the host starts the server as a local child process and talks over standard input/output, and **streamable HTTP**, used for remote servers. When a connection starts, client and server exchange an initialize handshake and advertise their capabilities.

## The three server primitives
1. **Tools** – functions the model can call, such as `search_knowledge_base(query)` or `save_note(title, content)`. Each tool has a name, a description and a JSON schema for its inputs. Tools are *model-controlled*: the LLM decides when to call them, usually with the user's approval.
2. **Resources** – read-only data the application can load into context, identified by a URI such as `notes://list` or `file:///report.pdf`. Resources are *application-controlled*.
3. **Prompts** – reusable prompt templates the server offers, for example "summarise this document". Prompts are *user-controlled* and often appear as slash commands.

## Building a server in Python
The official `mcp` Python SDK includes **FastMCP**, which turns ordinary Python functions into MCP tools with a decorator: type hints become the input schema and the docstring becomes the description. Running `mcp.run()` serves over stdio by default. A matching client (`ClientSession` with `stdio_client`) can launch the server, call `list_tools()` and `call_tool(name, arguments)`.

## Why MCP matters
MCP separates *capabilities* from *applications*. The same StudyPilot server can be used from Claude Desktop, from another agent, or from a script, without changing a line of server code. It also improves security, because the host controls which servers are connected and can ask the user to approve each tool call.

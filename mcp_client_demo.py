"""MCP client demo: launches mcp_server.py over stdio and calls its tools,
exactly like Claude Desktop (an MCP host) would.

Run:  python mcp_client_demo.py
"""
import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent
SERVER = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server.py")], cwd=str(ROOT))


def section(title: str) -> None:
    print("\n" + "=" * 70 + f"\n {title}\n" + "=" * 70)


def text_of(result) -> str:
    return "\n".join(getattr(c, "text", str(c)) for c in result.content)


async def main():
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            # mcp 2.x uses snake_case (server_info); 1.x used serverInfo
            server = getattr(info, "server_info", None) or getattr(info, "serverInfo")
            section(f"Connected to MCP server: {server.name}")

            tools = await session.list_tools()
            section(f"Tools exposed ({len(tools.tools)})")
            for t in tools.tools:
                print(f"  • {t.name:<22} {(t.description or '').splitlines()[0][:70]}")

            resources = await session.list_resources()
            print("\n  Resources:", ", ".join(str(r.uri) for r in resources.resources))

            section("call_tool: list_documents()")
            print(text_of(await session.call_tool("list_documents", {})))

            section('call_tool: search_knowledge_base("self-RAG", k=2)')
            print(text_of(await session.call_tool("search_knowledge_base", {"query": "self-RAG", "k": 2})))

            section('call_tool: ask_agent("What is MCP?")')
            print(text_of(await session.call_tool("ask_agent", {"question": "What is MCP?"})))

            section("read_resource: notes://list")
            res = await session.read_resource("notes://list")
            print("\n".join(getattr(c, "text", "") for c in res.contents))

    print("\nMCP demo finished ✅")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())

"""MCP handshake via official ClientSession (local stdio)."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HOME = r"D:\industry-graph-mcp"
PY = r"D:\anaconda3\python.exe"


async def main() -> None:
    os.environ["INDUSTRY_GRAPH_MCP_HOME"] = HOME
    params = StdioServerParameters(
        command=PY,
        args=["-m", "industry_graph_mcp", "mcp"],
        env={**os.environ, "INDUSTRY_GRAPH_MCP_HOME": HOME},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            # call ping
            result = await session.call_tool("ping", {})
            out = Path(HOME) / "cache" / "mcp_handshake.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "server": getattr(init, "serverInfo", None) and {
                    "name": init.serverInfo.name,
                    "version": init.serverInfo.version,
                },
                "tools": names,
                "ping": [c.model_dump() if hasattr(c, "model_dump") else str(c) for c in result.content],
            }
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            print("OK tools=", len(names))
            print("wrote", out)


if __name__ == "__main__":
    asyncio.run(main())

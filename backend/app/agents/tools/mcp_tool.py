"""MCP client tools: call user-configured MCP servers (settings → MCP servers)."""
import asyncio
import json

from app import models
from app.agents.tools import ToolSpec


def _configured_servers(ctx) -> dict:
    with ctx.session_factory() as s:
        row = s.get(models.AppSetting, "mcp_servers")
        return json.loads(row.value_json) if row else {}


def _server_or_error(ctx, name: str):
    servers = _configured_servers(ctx)
    if name not in servers:
        configured = sorted(servers) or ["none configured — add servers in Settings → MCP"]
        return None, {"error": f"MCP server '{name}' not configured. Configured: {configured}"}
    return servers[name], None


async def _with_session(server: dict, action):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    url = server["url"]
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await action(session)


def mcp_list_tools(args, ctx):
    server, error = _server_or_error(ctx, args["server"])
    if error:
        return error

    async def action(session):
        result = await session.list_tools()
        return [
            {"name": t.name, "description": t.description or ""} for t in result.tools
        ]

    tools = asyncio.run(_with_session(server, action))
    return {"tools": tools}


def mcp_call_tool(args, ctx):
    server, error = _server_or_error(ctx, args["server"])
    if error:
        return error

    async def action(session):
        result = await session.call_tool(args["tool"], args.get("arguments") or {})
        parts = []
        for block in result.content:
            parts.append(getattr(block, "text", str(block)))
        return "\n".join(parts)

    output = asyncio.run(_with_session(server, action))
    return {"result": output[:8000]}


SPECS = [
    ToolSpec(
        name="mcp_list_tools",
        description="List tools exposed by a configured MCP server (Settings → MCP servers).",
        input_schema={
            "type": "object",
            "properties": {"server": {"type": "string"}},
            "required": ["server"],
        },
        fn=mcp_list_tools,
    ),
    ToolSpec(
        name="mcp_call_tool",
        description="Call a tool on a configured MCP server.",
        input_schema={
            "type": "object",
            "properties": {
                "server": {"type": "string"},
                "tool": {"type": "string"},
                "arguments": {"type": "object"},
            },
            "required": ["server", "tool"],
        },
        fn=mcp_call_tool,
    ),
]

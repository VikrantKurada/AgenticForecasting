"""Keyless web search via DuckDuckGo (ddgs)."""
from app.agents.tools import ToolSpec


def _ddgs_search(query: str, max_results: int) -> list[dict]:
    from ddgs import DDGS

    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


def web_search(args, ctx):
    results = _ddgs_search(args["query"], int(args.get("max_results", 5)))
    return {
        "results": [
            {
                "title": r.get("title", ""),
                "url": r.get("href", r.get("url", "")),
                "snippet": r.get("body", "")[:500],
            }
            for r in results
        ]
    }


SPECS = [
    ToolSpec(
        name="web_search",
        description=(
            "Search the web for recent news, data releases, or context "
            "(e.g. geopolitical events, central bank announcements)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        fn=web_search,
    ),
]

"""Generic HTTPS GET for public APIs the agent decides to consult."""
import httpx

from app.agents.tools import ToolSpec

MAX_BYTES = 262_144
MAX_RETURN_CHARS = 8_000


def http_get(args, ctx):
    url = args["url"]
    if not url.lower().startswith("https://"):
        return {"error": "Only https:// URLs are allowed."}
    with httpx.Client(follow_redirects=True, timeout=15) as client:
        resp = client.get(url, headers={"User-Agent": "AgenticForecasting/0.1"})
    body = resp.content[:MAX_BYTES]
    text = body.decode(resp.encoding or "utf-8", errors="replace")
    return {
        "status_code": resp.status_code,
        "content_type": resp.headers.get("content-type", ""),
        "truncated": len(resp.content) > MAX_RETURN_CHARS,
        "body": text[:MAX_RETURN_CHARS],
    }


SPECS = [
    ToolSpec(
        name="http_get",
        description="Fetch a public HTTPS URL (JSON API or page). Body truncated to 8000 chars.",
        input_schema={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        fn=http_get,
    ),
]

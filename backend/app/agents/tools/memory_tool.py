"""Agent-facing semantic memory: save durable facts, recall relevant knowledge."""
from app.agents.tools import ToolSpec


def save_fact(args, ctx):
    item_id = ctx.memory.add_fact(args["content"], project_id=ctx.project_id)
    return {"status": "saved", "id": item_id}


def recall_memory(args, ctx):
    facts = ctx.memory.semantic_facts(args["query"], project_id=ctx.project_id)
    episodes = ctx.memory.recent_episodes(ctx.project_id, limit=3) if ctx.project_id else []
    return {
        "facts": [{"content": f.content, "created_at": f.created_at} for f in facts],
        "recent_episodes": [e.content[:400] for e in episodes],
    }


SPECS = [
    ToolSpec(
        name="save_fact",
        description=(
            "Save a durable fact to semantic memory (indicator definitions, country "
            "context, data quirks) for future runs."
        ),
        input_schema={
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        },
        fn=save_fact,
    ),
    ToolSpec(
        name="recall_memory",
        description="Recall relevant facts and recent forecasting episodes from memory.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        fn=recall_memory,
    ),
]

"""Search and fetch economic series across all configured connectors."""
from app.agents.tools import ToolSpec


def search_series(args, ctx):
    query = args["query"]
    source = args.get("source")
    limit = int(args.get("limit", 5))
    sources = [source] if source else list(ctx.connectors)
    results, errors = [], {}
    for name in sources:
        connector = ctx.connectors.get(name)
        if connector is None:
            errors[name] = "unknown source"
            continue
        try:
            for meta in connector.search(query, limit=limit):
                results.append(
                    {
                        "source": meta.source, "series_id": meta.series_id,
                        "title": meta.title, "frequency": meta.frequency, "units": meta.units,
                    }
                )
        except Exception as exc:
            errors[name] = str(exc)
    out = {"results": results}
    if errors:
        out["source_errors"] = errors
    return out


def fetch_series(args, ctx):
    source, series_id = args["source"], args["series_id"]
    connector = ctx.connectors.get(source)
    if connector is None:
        return {"error": f"Unknown source '{source}'. Available: {sorted(ctx.connectors)}"}
    data = connector.fetch(series_id, **(args.get("params") or {}))
    key = f"{source}:{series_id}"
    ctx.data_store[key] = data
    non_null = [o for o in data.observations if o[1] is not None]
    return {
        "series_key": key,
        "source": source,
        "series_id": series_id,
        "title": data.meta.title,
        "count": len(data.observations),
        "start": data.observations[0][0] if data.observations else None,
        "end": data.observations[-1][0] if data.observations else None,
        "latest_value": non_null[-1][1] if non_null else None,
        "observations_tail": data.observations[-40:],
        "note": "Full series stored under series_key for run_model and build_chart.",
    }


SPECS = [
    ToolSpec(
        name="search_series",
        description=(
            "Search for economic time series across data sources (fred, worldbank, imf, "
            "bls, ecb, oecd). Returns series ids to pass to fetch_series."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords, e.g. 'us real gdp'"},
                "source": {"type": "string", "description": "Optional: restrict to one source"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        fn=search_series,
    ),
    ToolSpec(
        name="fetch_series",
        description=(
            "Fetch a series' observations. Stores the full series under a series_key "
            "for later run_model / build_chart calls; returns a summary plus the recent tail."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "series_id": {"type": "string"},
                "params": {"type": "object", "description": "Optional source-specific params"},
            },
            "required": ["source", "series_id"],
        },
        fn=fetch_series,
    ),
]

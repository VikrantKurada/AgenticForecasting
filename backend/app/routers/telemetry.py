import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func

from app import models
from app.deps import get_db

router = APIRouter(prefix="/api", tags=["telemetry"])


@router.get("/runs/{run_id}/trace")
def run_trace(run_id: str, db=Depends(get_db)):
    rows = (
        db.query(models.Event)
        .filter_by(run_id=run_id)
        .order_by(models.Event.ts.asc())
        .all()
    )
    if not rows:
        run = db.get(models.Run, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")

    nodes = [
        {
            "id": r.id, "span_id": r.span_id, "parent_span_id": r.parent_span_id,
            "actor": r.actor, "event_type": r.event_type,
            "payload": json.loads(r.payload_json), "ts": r.ts, "children": [],
        }
        for r in rows
    ]
    by_span: dict[str, dict] = {}
    for node in nodes:
        by_span.setdefault(node["span_id"], node)
    roots = []
    for node in nodes:
        parent = by_span.get(node["parent_span_id"]) if node["parent_span_id"] else None
        if parent is not None and parent is not node:
            parent["children"].append(node)
        else:
            roots.append(node)
    return {"run_id": run_id, "spans": roots}


@router.get("/projects/{project_id}/usage")
def project_usage(project_id: str, db=Depends(get_db)):
    totals = (
        db.query(
            func.coalesce(func.sum(models.TokenUsage.input_tokens), 0),
            func.coalesce(func.sum(models.TokenUsage.output_tokens), 0),
            func.coalesce(func.sum(models.TokenUsage.est_cost_usd), 0.0),
        )
        .filter(models.TokenUsage.project_id == project_id)
        .one()
    )

    def grouped(column, label):
        rows = (
            db.query(
                column,
                func.sum(models.TokenUsage.input_tokens),
                func.sum(models.TokenUsage.output_tokens),
                func.sum(models.TokenUsage.est_cost_usd),
                func.count(models.TokenUsage.id),
            )
            .filter(models.TokenUsage.project_id == project_id)
            .group_by(column)
            .all()
        )
        return [
            {label: value, "input_tokens": int(i), "output_tokens": int(o),
             "est_cost_usd": float(c), "calls": int(n)}
            for value, i, o, c, n in rows
        ]

    samples = (
        db.query(models.ResourceSample)
        .filter_by(project_id=project_id)
        .order_by(models.ResourceSample.ts.desc())
        .limit(200)
        .all()
    )
    cpu = [s.cpu_percent for s in samples]
    mem = [s.mem_percent for s in samples]
    gpu = [s.gpu_util for s in samples if s.gpu_util is not None]

    run_counts = dict(
        db.query(models.Run.status, func.count(models.Run.id))
        .filter(models.Run.project_id == project_id)
        .group_by(models.Run.status)
        .all()
    )

    return {
        "tokens": {
            "total_input": int(totals[0]),
            "total_output": int(totals[1]),
            "est_cost_usd": float(totals[2]),
            "by_provider": grouped(models.TokenUsage.provider, "provider"),
            "by_model": grouped(models.TokenUsage.model, "model"),
            "by_role": grouped(models.TokenUsage.agent_role, "agent_role"),
        },
        "resources": {
            "avg_cpu": sum(cpu) / len(cpu) if cpu else 0.0,
            "avg_mem": sum(mem) / len(mem) if mem else 0.0,
            "avg_gpu": sum(gpu) / len(gpu) if gpu else None,
            "samples": [
                {"ts": s.ts, "cpu": s.cpu_percent, "mem": s.mem_percent,
                 "gpu": s.gpu_util, "gpu_mem": s.gpu_mem}
                for s in reversed(samples)
            ],
        },
        "runs": {
            "total": sum(run_counts.values()),
            "completed": run_counts.get("completed", 0),
            "failed": run_counts.get("failed", 0),
            "running": run_counts.get("running", 0) + run_counts.get("planning", 0),
        },
    }


@router.get("/projects/{project_id}/events")
def project_events(
    project_id: str, limit: int = 50, offset: int = 0, actor: str | None = None,
    db=Depends(get_db),
):
    query = db.query(models.Event).filter_by(project_id=project_id)
    if actor:
        query = query.filter_by(actor=actor)
    total = query.count()
    rows = query.order_by(models.Event.ts.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "events": [
            {"id": r.id, "run_id": r.run_id, "actor": r.actor, "event_type": r.event_type,
             "payload": json.loads(r.payload_json), "ts": r.ts}
            for r in rows
        ],
    }

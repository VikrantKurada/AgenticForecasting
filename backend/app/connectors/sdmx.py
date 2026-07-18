"""Shared parser for SDMX-JSON payloads (ECB 1.0 shape and OECD 'data'-wrapped shape)."""
from app.connectors.base import ConnectorError


def parse_sdmx_observations(payload: dict, series_id: str) -> list[tuple]:
    root = payload.get("data", payload)
    datasets = root.get("dataSets") or []
    if not datasets:
        raise ConnectorError(f"SDMX response has no dataSets for {series_id}")

    structure = root.get("structure")
    if structure is None:
        structures = root.get("structures") or []
        structure = structures[0] if structures else None
    if structure is None:
        raise ConnectorError(f"SDMX response has no structure for {series_id}")

    obs_dims = structure.get("dimensions", {}).get("observation", [])
    time_values = []
    for dim in obs_dims:
        if dim.get("id") in ("TIME_PERIOD", "TIME"):
            time_values = [v["id"] for v in dim.get("values", [])]
            break

    series_map = datasets[0].get("series") or {}
    if not series_map:
        # Flat (no series dimensions) datasets keep observations at dataset level
        obs = datasets[0].get("observations") or {}
    else:
        first_key = next(iter(series_map))
        obs = series_map[first_key].get("observations") or {}

    observations = []
    for index_str, values in obs.items():
        idx = int(index_str)
        date = time_values[idx] if idx < len(time_values) else str(idx)
        value = values[0] if values else None
        observations.append((date, float(value) if value is not None else None))
    observations.sort(key=lambda t: t[0])
    if not observations:
        raise ConnectorError(f"SDMX response has no observations for {series_id}")
    return observations

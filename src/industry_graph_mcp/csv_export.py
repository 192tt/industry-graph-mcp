"""Write company nodes of a scope to a UTF-8 CSV with Beijing-style Chinese headers."""

from __future__ import annotations

import csv
import re
from typing import Any

from industry_graph_mcp.config import data_dir
from industry_graph_mcp.schema import STANDARD_HEADERS, normalize_props, props_to_csv_row


def csv_path_for_scope(scope: str):
    safe = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", (scope or "default").strip()) or "default"
    folder = data_dir() / "csv"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{safe}.csv"


def export_scope_csv(store, scope: str, limit: int = 200000) -> dict[str, Any]:
    """Rewrite data/csv/{scope}.csv using standardized Chinese headers."""
    nodes = store.query_nodes(label="Company", scope=scope, limit=limit)
    rows: list[dict[str, str]] = []
    for i, node in enumerate(nodes, 1):
        props = normalize_props(node.get("properties") or {})
        props.setdefault("name", props.get("name") or node.get("id") or "")
        rows.append(props_to_csv_row(i, props))
    path = csv_path_for_scope(scope)
    try:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=STANDARD_HEADERS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    except PermissionError:
        # File may be open in Excel/IDE — write sibling and keep going
        path = path.with_name(path.stem + "_标准.csv")
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=STANDARD_HEADERS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    return {
        "csv": str(path),
        "companies": len(rows),
        "scope": scope,
        "columns": list(STANDARD_HEADERS),
    }

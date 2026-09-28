"""Public patent mention discovery via search queries."""

from __future__ import annotations

from typing import Any

from industry_graph_mcp.search_fetch import do_search


def search_patents(company_or_topic: str, num: int = 8) -> list[dict[str, Any]]:
    query = f"{company_or_topic} 专利 公开"
    results = do_search(query, num=num)
    for r in results:
        if isinstance(r, dict) and "error" not in r:
            r["source_type"] = "patent"
            r["query"] = query
    return results

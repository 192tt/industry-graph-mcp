"""Public tender / bid announcement discovery via search queries."""

from __future__ import annotations

from typing import Any

from industry_graph_mcp.search_fetch import do_search


def search_tenders(region: str, industry: str, num: int = 8) -> list[dict[str, Any]]:
    query = f"{region} {industry} 中标 公告 政府采购"
    results = do_search(query, num=num)
    for r in results:
        if isinstance(r, dict) and "error" not in r:
            r["source_type"] = "tender"
            r["query"] = query
    return results

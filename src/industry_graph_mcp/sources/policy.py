"""Public policy discovery via search queries."""

from __future__ import annotations

from typing import Any

from industry_graph_mcp.search_fetch import do_search


def search_policies(region: str, industry: str, num: int = 8) -> list[dict[str, Any]]:
    """Search public policy mentions; returns list of {title, href, body, query, source_type}."""
    queries = [
        f"{region} {industry} 产业政策 site:gov.cn",
        f"{region} {industry} 高新技术 政策 site:gov.cn",
        f"{region} {industry} 发展规划 意见 通知",
    ]
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    per = max(3, (num + len(queries) - 1) // len(queries))
    for query in queries:
        results = do_search(query, num=per)
        for r in results:
            if not isinstance(r, dict) or r.get("error"):
                continue
            key = str(r.get("href") or r.get("url") or r.get("title") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            item = dict(r)
            item["source_type"] = "policy"
            item["query"] = query
            out.append(item)
            if len(out) >= num:
                return out
    return out

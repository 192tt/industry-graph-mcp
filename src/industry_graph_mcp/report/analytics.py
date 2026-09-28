"""Graph-derived analytics for insight reports."""

from __future__ import annotations

from collections import Counter
from typing import Any

from industry_graph_mcp.enrich import (
    _GENERIC_SUB,
    clean_company_name,
    infer_role,
    infer_sub_industry,
)


def analyze_scope(store, scope: str, top_n: int = 30) -> dict[str, Any]:
    """Compute distributional stats from GraphStore for a scope."""
    nodes = store.query_nodes(scope=scope, limit=100000)
    edges = store.query_relations(scope=scope, limit=200000)

    companies = [n for n in nodes if "Company" in (n.get("labels") or [])]
    industries = [n for n in nodes if "Industry" in (n.get("labels") or [])]
    regions = [n for n in nodes if "Region" in (n.get("labels") or [])]

    sub_industry: Counter[str] = Counter()
    sub_inferred: Counter[str] = Counter()
    role: Counter[str] = Counter()
    role_inferred: Counter[str] = Counter()
    district: Counter[str] = Counter()
    source: Counter[str] = Counter()

    for c in companies:
        props = c.get("properties") or {}
        name = clean_company_name(str(props.get("name") or c["id"]))
        raw_sub = props.get("sub_industry") or props.get("industry") or "未标注细分"
        sub_industry[str(raw_sub)] += 1
        inferred = infer_sub_industry(name, props)
        sub_inferred[inferred] += 1
        role[str(props.get("role") or "未标注角色")] += 1
        role_inferred[infer_role(name, props)] += 1
        if props.get("district"):
            district[str(props["district"])] += 1
        src = props.get("source") or props.get("source_type") or "未标注来源"
        source[str(src)[:40]] += 1

    rel_types = Counter(e.get("rel_type") or "RELATED" for e in edges)

    degree: Counter[str] = Counter()
    for e in edges:
        degree[str(e.get("source_id") or "")] += 1
        degree[str(e.get("target_id") or "")] += 1
    company_ids = {c["id"] for c in companies}
    top_degree = [
        {"id": nid, "degree": deg}
        for nid, deg in degree.most_common()
        if nid in company_ids
    ][:top_n]

    by_id = {c["id"]: c for c in companies}
    top_companies = []
    for item in top_degree:
        node = by_id.get(item["id"], {})
        props = node.get("properties") or {}
        name = clean_company_name(str(props.get("name") or item["id"]))
        top_companies.append(
            {
                "name": name,
                "id": item["id"],
                "degree": item["degree"],
                "sub_industry": infer_sub_industry(name, props),
                "role": infer_role(name, props),
                "district": props.get("district") or "",
                "source": (props.get("source") or "")[:60],
            }
        )

    if len(top_companies) < min(10, len(companies)):
        ranked = sorted(
            companies,
            key=lambda c: (
                0 if infer_role(clean_company_name(str((c.get("properties") or {}).get("name") or c["id"])), c.get("properties") or {}) in ("龙头", "独角兽") else 1,
                (c.get("properties") or {}).get("name") or c["id"],
            ),
        )
        seen = {t["id"] for t in top_companies}
        for c in ranked:
            if c["id"] in seen:
                continue
            props = c.get("properties") or {}
            name = clean_company_name(str(props.get("name") or c["id"]))
            top_companies.append(
                {
                    "name": name,
                    "id": c["id"],
                    "degree": degree.get(c["id"], 0),
                    "sub_industry": infer_sub_industry(name, props),
                    "role": infer_role(name, props),
                    "district": props.get("district") or "",
                    "source": (props.get("source") or "")[:60],
                }
            )
            if len(top_companies) >= top_n:
                break

    focus_ids = {t["id"] for t in top_companies}
    for n in industries + regions:
        focus_ids.add(n["id"])
    focus_edges = [
        e
        for e in edges
        if e.get("source_id") in focus_ids or e.get("target_id") in focus_ids
    ]

    return {
        "scope": scope,
        "nodes_total": len(nodes),
        "edges_total": len(edges),
        "companies": len(companies),
        "industry_nodes": len(industries),
        "region_nodes": len(regions),
        "sub_industry": sub_industry.most_common(20),
        "sub_industry_inferred": sub_inferred.most_common(20),
        "role": role.most_common(15),
        "role_inferred": role_inferred.most_common(15),
        "district": district.most_common(15),
        "source": source.most_common(15),
        "rel_types": rel_types.most_common(20),
        "top_companies": top_companies,
        "focus_ids": list(focus_ids),
        "focus_edges": focus_edges[:5000],
        "hub_nodes": industries + regions,
        "sample_nodes": nodes,
        "sample_edges": focus_edges[:5000],
        "generic_sub_set": sorted(_GENERIC_SUB),
    }

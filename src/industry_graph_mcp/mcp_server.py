"""stdio MCP server — tools run on the user's machine (D: data root)."""

from __future__ import annotations

import csv
import io
import json
import webbrowser
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from industry_graph_mcp import __version__
from industry_graph_mcp.config import data_dir, load_config, reports_dir
from industry_graph_mcp.graph.store import get_store
from industry_graph_mcp.report import build_insight_report, list_reports, save_report
from industry_graph_mcp.search_fetch import do_fetch, do_search, survey_plan
from industry_graph_mcp.discover import discover_companies as discover_companies_impl
from industry_graph_mcp.sources import patent as patent_src
from industry_graph_mcp.sources import policy as policy_src
from industry_graph_mcp.sources import tender as tender_src

mcp = FastMCP(
    "industry-graph-mcp",
    instructions=(
        "本地产业图谱 MCP：用用户侧 AI 编排调研；搜索/建图/报告均在本机。"
        "数据目录默认 D:\\industry-graph-mcp。"
        "用户要求尽可能多的企业：必须用 discover_companies(maximize=True, max_companies=500+)，"
        "批量入库后若还能搜到新名就继续，不要在几十家时停止。"
        "批量高新名单常缺细分/角色：入库时自动补全；也可调用 graph_enrich_fields(scope) 回写。"
        "入库默认 enrich_profile=True：公开检索补电话/信用代码/法人/地址/产品等标准字段，并写 data/csv/{scope}.csv。"
        "旧数据继续补：enrich_company_profiles(scope, limit=50) 可反复调用直到补完。"
        "洞察报告主交付物是 Markdown（reports/.../REPORT.md），用 generate_insight_report："
        "模板=国内产业政策解读（概述/背景/内容/影响/建议）+ 区域产业样本洞察（统计图/图谱/企业）。"
        "无 Neo4j 时使用 SQLite 平替。详见 SKILL.md。"
    ),
)


def _store():
    return get_store()


@mcp.tool()
def ping() -> dict[str, Any]:
    """Health check: version, config backend, data paths."""
    cfg = load_config()
    store = _store()
    try:
        st = store.stats()
    finally:
        store.close()
    return {
        "ok": True,
        "version": __version__,
        "graph_backend": cfg.graph_backend,
        "effective_backend": st.get("backend"),
        "stats": st,
        "data_dir": str(data_dir()),
        "reports_dir": str(reports_dir()),
    }


@mcp.tool()
def survey_plan_tool(utterance: str, target_companies: int = 500) -> dict[str, Any]:
    """Parse survey intent. Default target_companies=500 — maximize public coverage."""
    return survey_plan(utterance, target_companies=target_companies)


@mcp.tool()
def discover_companies(
    region: str,
    industry: str,
    max_companies: int = 500,
    results_per_query: int = 15,
    fetch_top_pages: int = 12,
    maximize: bool = True,
) -> dict[str, Any]:
    """Discover as many company candidates as possible via multi-query search + list-page fetch."""
    return discover_companies_impl(
        region=region,
        industry=industry,
        max_companies=max_companies,
        results_per_query=results_per_query,
        fetch_top_pages=fetch_top_pages,
        maximize=maximize,
    )


@mcp.tool()
def graph_upsert_companies_batch(
    companies_json: str,
    scope: str = "default",
    labels_csv: str = "Company",
    enrich_profile: bool = True,
    profile_fetch_pages: int = 1,
) -> dict[str, Any]:
    """Batch upsert companies and (by default) publicly enrich full profile fields + rewrite CSV."""
    items = json.loads(companies_json or "[]")
    if not isinstance(items, list):
        return {"error": "companies_json must be a JSON array"}
    labels = [x.strip() for x in labels_csv.split(",") if x.strip()] or ["Company"]
    store = _store()
    ok = 0
    skipped = 0
    profiled = 0
    try:
        from industry_graph_mcp.company_profile import enrich_company_profile
        from industry_graph_mcp.enrich import enrich_company_props
        from industry_graph_mcp.schema import normalize_props

        region_hint = ""
        industry_hint = "科技"
        if "_" in scope:
            region_hint, industry_hint = scope.split("_", 1)
        for item in items:
            if isinstance(item, str):
                name = item.strip()
                props: dict[str, Any] = {"name": name}
            elif isinstance(item, dict):
                name = str(item.get("name") or item.get("id") or "").strip()
                props = dict(item.get("properties") or {})
                for k, v in item.items():
                    if k not in ("name", "id", "properties", "labels", "scope") and v not in (None, ""):
                        props.setdefault(k, v)
                props.setdefault("name", name)
            else:
                skipped += 1
                continue
            if not name:
                skipped += 1
                continue
            props = normalize_props(props)
            if enrich_profile:
                props = enrich_company_profile(
                    name,
                    props,
                    region=region_hint,
                    industry=industry_hint or "科技",
                    fetch_pages=profile_fetch_pages,
                )
                profiled += 1
            else:
                props = enrich_company_props(
                    name, props, default_region=region_hint, default_industry=industry_hint or "科技"
                )
            store.upsert_node(name, labels=labels, properties=props, scope=scope)
            ok += 1
        from industry_graph_mcp.csv_export import export_scope_csv

        csv_meta = export_scope_csv(store, scope) if ok else None
        return {
            "imported": ok,
            "skipped": skipped,
            "profiled": profiled,
            "enrich_profile": enrich_profile,
            "scope": scope,
            "stats": store.stats(scope),
            "csv": csv_meta,
        }
    finally:
        store.close()


@mcp.tool()
def graph_enrich_fields(
    scope: str,
    write_back: bool = True,
    add_sub_edges: bool = True,
    default_region: str = "",
    default_industry: str = "科技",
) -> dict[str, Any]:
    """Backfill sub_industry/role for companies in a scope (name-keyword rules)."""
    from industry_graph_mcp.enrich import enrich_scope_companies

    if not default_region and "_" in scope:
        default_region, default_industry = scope.split("_", 1)
    store = _store()
    try:
        result = enrich_scope_companies(
            store,
            scope=scope,
            write_back=write_back,
            add_sub_edges=add_sub_edges,
            default_region=default_region,
            default_industry=default_industry or "科技",
        )
        if write_back:
            from industry_graph_mcp.csv_export import export_scope_csv

            result["csv"] = export_scope_csv(store, scope)
        return result
    finally:
        store.close()


@mcp.tool()
def enrich_company_profiles(
    scope: str,
    limit: int = 50,
    only_missing: bool = True,
    fetch_pages: int = 1,
    default_region: str = "",
    default_industry: str = "科技",
) -> dict[str, Any]:
    """
    Public-web enrich full company profile fields for a scope (phone/credit/legal/address/tech/...).
    Call repeatedly until updated=0. Each call also rewrites the standardized Chinese CSV.
    """
    from industry_graph_mcp.company_profile import enrich_scope_profiles
    from industry_graph_mcp.csv_export import export_scope_csv

    if not default_region and "_" in scope:
        default_region, default_industry = scope.split("_", 1)
    store = _store()
    try:
        result = enrich_scope_profiles(
            store,
            scope=scope,
            limit=max(1, min(limit, 200)),
            only_missing=only_missing,
            fetch_pages=fetch_pages,
            region=default_region,
            industry=default_industry or "科技",
        )
        result["csv"] = export_scope_csv(store, scope)
        return result
    finally:
        store.close()


@mcp.tool()
def graph_export_csv(scope: str) -> dict[str, Any]:
    """Export Company nodes in a scope to data/csv/{scope}.csv with Beijing-style Chinese headers."""
    from industry_graph_mcp.csv_export import export_scope_csv

    store = _store()
    try:
        return export_scope_csv(store, scope)
    finally:
        store.close()


@mcp.tool()
def web_search(query: str, num: int = 10) -> list[dict[str, Any]]:
    """DuckDuckGo web search (local, no API key)."""
    return do_search(query, num=num)


@mcp.tool()
def fetch_url(
    url: str,
    max_chars: int = 12000,
    strategy: str = "auto",
) -> dict[str, Any]:
    """Fetch and extract page text. strategy: auto|direct|jina|archive."""
    return do_fetch(url, max_chars=max_chars, strategy=strategy)


@mcp.tool()
def graph_upsert_company(
    company_name: str,
    properties_json: str = "{}",
    scope: str = "default",
    labels_csv: str = "Company",
) -> dict[str, Any]:
    """Upsert a company node with public profile enrichment and CSV rewrite."""
    props = json.loads(properties_json or "{}")
    props.setdefault("name", company_name)
    from industry_graph_mcp.company_profile import enrich_company_profile
    from industry_graph_mcp.schema import normalize_props

    region_hint, industry_hint = "", "科技"
    if "_" in scope:
        region_hint, industry_hint = scope.split("_", 1)
    props = enrich_company_profile(
        company_name,
        normalize_props(props),
        region=region_hint,
        industry=industry_hint or "科技",
    )
    labels = [x.strip() for x in labels_csv.split(",") if x.strip()] or ["Company"]
    store = _store()
    try:
        node = store.upsert_node(company_name, labels=labels, properties=props, scope=scope)
        from industry_graph_mcp.csv_export import export_scope_csv

        node["csv"] = export_scope_csv(store, scope)
        return node
    finally:
        store.close()


@mcp.tool()
def graph_add_relation(
    source_id: str,
    target_id: str,
    rel_type: str,
    properties_json: str = "{}",
    scope: str = "default",
) -> dict[str, Any]:
    """Add a directed relation between two nodes."""
    props = json.loads(properties_json or "{}")
    store = _store()
    try:
        return store.add_relation(source_id, target_id, rel_type, props, scope)
    finally:
        store.close()


@mcp.tool()
def graph_query(
    label: str = "",
    scope: str = "",
    where_json: str = "{}",
    limit: int = 50,
) -> dict[str, Any]:
    """Query nodes; optional label/scope/where_json filter."""
    where = json.loads(where_json or "{}")
    store = _store()
    try:
        nodes = store.query_nodes(
            label=label or None,
            scope=scope or None,
            where=where or None,
            limit=limit,
        )
        return {"count": len(nodes), "nodes": nodes}
    finally:
        store.close()


@mcp.tool()
def graph_query_relations(
    source_id: str = "",
    target_id: str = "",
    rel_type: str = "",
    scope: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """Query relations with optional filters."""
    store = _store()
    try:
        edges = store.query_relations(
            source_id=source_id or None,
            target_id=target_id or None,
            rel_type=rel_type or None,
            scope=scope or None,
            limit=limit,
        )
        return {"count": len(edges), "edges": edges}
    finally:
        store.close()


@mcp.tool()
def graph_delete(
    node_id: str = "",
    source_id: str = "",
    target_id: str = "",
    rel_type: str = "",
    scope: str = "",
) -> dict[str, Any]:
    """Delete a node (by node_id) or relation (by source_id+target_id)."""
    store = _store()
    try:
        if node_id:
            ok = store.delete_node(node_id, scope or None)
            return {"deleted_node": ok, "node_id": node_id}
        if source_id and target_id:
            n = store.delete_relation(source_id, target_id, rel_type or None, scope or None)
            return {"deleted_relations": n}
        return {"error": "provide node_id or source_id+target_id"}
    finally:
        store.close()


@mcp.tool()
def graph_stats(scope: str = "") -> dict[str, Any]:
    """Graph statistics for optional scope."""
    store = _store()
    try:
        return store.stats(scope or None)
    finally:
        store.close()


@mcp.tool()
def graph_export(scope: str = "", out_name: str = "") -> dict[str, Any]:
    """Export graph JSON to D:\\industry-graph-mcp\\data."""
    store = _store()
    try:
        data = store.export_graph(scope or None)
    finally:
        store.close()
    name = out_name or f"export_{(scope or 'all')}.json"
    path = data_dir() / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(path), "nodes": len(data.get("nodes", [])), "edges": len(data.get("edges", []))}


@mcp.tool()
def graph_import_csv(
    csv_text: str,
    scope: str = "default",
    name_column: str = "企业名称",
) -> dict[str, Any]:
    """Import companies from CSV text. Uses name_column as node id/name."""
    from industry_graph_mcp.enrich import enrich_company_props

    reader = csv.DictReader(io.StringIO(csv_text))
    store = _store()
    count = 0
    region_hint, industry_hint = "", "科技"
    if "_" in scope:
        region_hint, industry_hint = scope.split("_", 1)
    try:
        for row in reader:
            name = (row.get(name_column) or row.get("name") or "").strip()
            if not name:
                continue
            props = {k: v for k, v in row.items() if v not in (None, "")}
            props["name"] = name
            props = enrich_company_props(
                name, props, default_region=region_hint, default_industry=industry_hint or "科技"
            )
            store.upsert_node(name, labels=["Company"], properties=props, scope=scope)
            count += 1
        from industry_graph_mcp.csv_export import export_scope_csv

        csv_meta = export_scope_csv(store, scope) if count else None
        return {"imported": count, "scope": scope, "csv": csv_meta}
    finally:
        store.close()


@mcp.tool()
def graph_import_json(
    nodes_json: str,
    edges_json: str = "[]",
    scope: str = "default",
) -> dict[str, Any]:
    """Import nodes/edges from JSON arrays."""
    nodes = json.loads(nodes_json or "[]")
    edges = json.loads(edges_json or "[]")
    store = _store()
    try:
        return store.import_nodes_edges(nodes, edges, scope=scope)
    finally:
        store.close()


@mcp.tool()
def graph_open_viewer(scope: str = "") -> dict[str, Any]:
    """Write graph JSON next to HTML viewer and open it in the default browser."""
    store = _store()
    try:
        data = store.export_graph(scope or None)
    finally:
        store.close()
    viewer_src = Path(__file__).resolve().parent / "graph" / "viewer" / "graph_viewer.html"
    out_dir = data_dir() / "viewer"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "graph_viewer.html"
    json_path = out_dir / "graph_data.json"
    html_path.write_text(viewer_src.read_text(encoding="utf-8"), encoding="utf-8")
    json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    webbrowser.open(html_path.as_uri())
    return {"html": str(html_path), "data": str(json_path), "nodes": len(data["nodes"]), "edges": len(data["edges"])}


@mcp.tool()
def generate_insight_report(
    scope: str,
    title: str = "",
    region: str = "",
    industry: str = "",
    narrative: str = "",
    max_table: int = 30,
    open_html: bool = False,
    auto_enrich: bool = True,
    include_policies: bool = True,
    policy_num: int = 8,
    policies_json: str = "[]",
) -> dict[str, Any]:
    """Generate Markdown-primary report: 产业政策解读模板 + 区域产业样本洞察（图/表/图谱）。"""
    policies = json.loads(policies_json or "[]")
    if not isinstance(policies, list):
        policies = []
    store = _store()
    try:
        return build_insight_report(
            store,
            scope=scope,
            title=title or None,
            region=region,
            industry=industry,
            narrative=narrative,
            max_table=max_table,
            open_html=open_html,
            auto_enrich=auto_enrich,
            include_policies=include_policies,
            policy_num=policy_num,
            policies=policies or None,
        )
    finally:
        store.close()


@mcp.tool()
def save_report_tool(
    title: str,
    content: str,
    scope: str = "default",
    meta_json: str = "{}",
) -> dict[str, Any]:
    """Save a free-form markdown note under D:\\industry-graph-mcp\\reports."""
    meta = json.loads(meta_json or "{}")
    return save_report(title=title, content=content, scope=scope, meta=meta)


@mcp.tool()
def list_reports_tool(scope: str = "", limit: int = 20) -> list[dict[str, Any]]:
    """List saved reports on D:."""
    return list_reports(scope=scope or None, limit=limit)


@mcp.tool()
def search_tenders(region: str, industry: str, num: int = 8) -> list[dict[str, Any]]:
    """Search public tender/bid announcements via web search queries."""
    return tender_src.search_tenders(region, industry, num=num)


@mcp.tool()
def search_patents(company_or_topic: str, num: int = 8) -> list[dict[str, Any]]:
    """Search public patent mentions via web search."""
    return patent_src.search_patents(company_or_topic, num=num)


@mcp.tool()
def search_policies(region: str, industry: str, num: int = 8) -> list[dict[str, Any]]:
    """Search public industry policies via web search."""
    return policy_src.search_policies(region, industry, num=num)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

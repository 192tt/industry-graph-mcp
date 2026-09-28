"""Tests for planning and company name extraction."""

from __future__ import annotations

import os

os.environ["INDUSTRY_GRAPH_MCP_HOME"] = r"D:\industry-graph-mcp\test_home"


def test_survey_plan_hangzhou_tech():
    from industry_graph_mcp.search_fetch import survey_plan

    plan = survey_plan("调研杭州的科技企业")
    assert plan["region"] == "杭州"
    assert plan["industry"] == "科技"
    assert plan["scope"] == "杭州_科技"
    assert plan["target_companies"] >= 500
    assert plan.get("goal")
    assert plan["queries_total"] >= 20


def test_extract_company_names():
    from industry_graph_mcp.discover import extract_company_names

    text = (
        "阿里巴巴（中国）有限公司、杭州海康威视数字技术股份有限公司入选名单。"
        "另有浙江大华技术股份有限公司。"
    )
    names = extract_company_names(text)
    assert "阿里巴巴（中国）有限公司" in names
    assert "杭州海康威视数字技术股份有限公司" in names
    assert "浙江大华技术股份有限公司" in names


def test_batch_upsert():
    import json
    from pathlib import Path

    from industry_graph_mcp.graph.sqlite_store import SqliteStore

    db = Path(r"D:\industry-graph-mcp\test_home\data\batch_test.db")
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    store = SqliteStore(db)
    try:
        for name in ["测试甲有限公司", "测试乙股份有限公司"]:
            store.upsert_node(name, properties={"name": name, "region": "杭州"}, scope="杭州_科技")
        st = store.stats("杭州_科技")
        assert st["nodes"] == 2
    finally:
        store.close()
        if db.exists():
            db.unlink()

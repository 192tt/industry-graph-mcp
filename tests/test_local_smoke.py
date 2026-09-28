"""Smoke tests for plan/report/config on D:."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ["INDUSTRY_GRAPH_MCP_HOME"] = r"D:\industry-graph-mcp\test_home"


def test_survey_plan():
    from industry_graph_mcp.search_fetch import survey_plan

    plan = survey_plan("我想调研一下广东的制造业")
    assert plan["region"] == "广东"
    assert plan["industry"] == "制造业"
    assert len(plan["queries"]) >= 3


def test_setup_sqlite_and_report():
    from industry_graph_mcp.report import save_report
    from industry_graph_mcp.setup_wizard import run_wizard

    cfg = run_wizard(backend="sqlite", non_interactive=True)
    assert cfg.graph_backend == "sqlite"
    assert Path(cfg.sqlite_path).as_posix().startswith("D:") or str(cfg.sqlite_path).startswith("D:")

    from industry_graph_mcp.graph.store import get_store

    store = get_store()
    try:
        store.upsert_node(
            "示例企业",
            properties={"name": "示例企业", "industry": "制造业"},
            scope="gd_manufacturing",
        )
        st = store.stats("gd_manufacturing")
        assert st["nodes"] >= 1
    finally:
        store.close()

    out = save_report(
        title="广东制造业烟雾测试",
        content="这是本地测试报告。\n\n样本口径：公开检索模拟。",
        scope="gd_manufacturing",
        meta={"backend": cfg.graph_backend},
    )
    assert Path(out["path"]).exists()
    assert "D:" in out["path"] or out["path"].startswith("D:")


def test_config_roundtrip():
    from industry_graph_mcp.config import load_config, save_config

    cfg = load_config()
    cfg.default_scope = "smoke"
    path = save_config(cfg)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["graph_backend"] in ("sqlite", "neo4j")

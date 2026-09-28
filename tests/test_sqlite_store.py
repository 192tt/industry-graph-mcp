"""Local SQLite graph store tests (D: temp dir)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Force D: home before importing package config helpers
os.environ["INDUSTRY_GRAPH_MCP_HOME"] = r"D:\industry-graph-mcp\test_home"


@pytest.fixture()
def store(tmp_path: Path):
    # Still keep DB file under D: project test area when possible
    db = Path(r"D:\industry-graph-mcp\test_home\data") / "pytest_graph.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    from industry_graph_mcp.graph.sqlite_store import SqliteStore

    s = SqliteStore(db)
    yield s
    s.close()
    if db.exists():
        db.unlink()


def test_upsert_and_query(store):
    store.upsert_node(
        "测试制造有限公司",
        labels=["Company"],
        properties={"name": "测试制造有限公司", "region": "广东"},
        scope="gd_test",
    )
    node = store.get_node("测试制造有限公司", scope="gd_test")
    assert node is not None
    assert node["properties"]["region"] == "广东"
    nodes = store.query_nodes(scope="gd_test")
    assert len(nodes) == 1


def test_relations_and_stats(store):
    store.upsert_node("A公司", properties={"name": "A公司"}, scope="s1")
    store.upsert_node("B公司", properties={"name": "B公司"}, scope="s1")
    store.add_relation("A公司", "B公司", "COMPETES_WITH", scope="s1")
    edges = store.query_relations(scope="s1")
    assert len(edges) == 1
    st = store.stats("s1")
    assert st["nodes"] == 2
    assert st["edges"] == 1
    assert st["backend"] == "sqlite"


def test_export_import(store):
    store.upsert_node("C公司", properties={"name": "C公司"}, scope="s2")
    data = store.export_graph("s2")
    store.delete_node("C公司", scope="s2")
    assert store.get_node("C公司", "s2") is None
    store.import_nodes_edges(data["nodes"], data["edges"], scope="s2")
    assert store.get_node("C公司", "s2") is not None

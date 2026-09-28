"""End-to-end local smoke without network search (graph + report + viewer files)."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ["INDUSTRY_GRAPH_MCP_HOME"] = r"D:\industry-graph-mcp"


def main() -> None:
    from industry_graph_mcp.setup_wizard import run_wizard
    from industry_graph_mcp.graph.store import get_store
    from industry_graph_mcp.report import save_report
    from industry_graph_mcp.search_fetch import survey_plan
    from industry_graph_mcp.config import data_dir

    print("1) setup sqlite on D:...")
    cfg = run_wizard(backend="sqlite", non_interactive=True)
    print("   backend=", cfg.graph_backend, "sqlite=", cfg.sqlite_path)

    print("2) survey plan...")
    plan = survey_plan("我想调研一下广东的制造业")
    print("   ", plan["region"], plan["industry"], plan["scope"])

    print("3) write sample graph...")
    store = get_store()
    try:
        for name in ["示例制造一厂", "示例制造二厂", "示例零部件公司"]:
            store.upsert_node(
                name,
                labels=["Company"],
                properties={"name": name, "region": "广东", "industry": "制造业"},
                scope=plan["scope"],
            )
        store.add_relation("示例制造一厂", "示例零部件公司", "SUPPLIER", scope=plan["scope"])
        store.add_relation("示例制造一厂", "示例制造二厂", "COMPETES_WITH", scope=plan["scope"])
        st = store.stats(plan["scope"])
        print("   stats=", st)
        data = store.export_graph(plan["scope"])
    finally:
        store.close()

    viewer_dir = data_dir() / "viewer"
    viewer_dir.mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "src" / "industry_graph_mcp" / "graph" / "viewer" / "graph_viewer.html"
    (viewer_dir / "graph_viewer.html").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (viewer_dir / "graph_data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print("4) viewer files:", viewer_dir)

    out = save_report(
        title="广东制造业本地烟雾测试",
        content=(
            "## 样本口径\n公开检索模拟数据（本地测试）。\n\n"
            "## 企业\n- 示例制造一厂\n- 示例制造二厂\n- 示例零部件公司\n"
        ),
        scope=plan["scope"],
        meta={"nodes": st["nodes"], "edges": st["edges"]},
    )
    print("5) report=", out["path"])
    print("OK")


if __name__ == "__main__":
    main()

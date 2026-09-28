# Industry Graph MCP

本地产业知识图谱 MCP：用户侧 AI 编排调研；搜索/建图/报告在本机；**仅安装包从你的服务器分发**。

- 默认数据根目录：`D:\industry-graph-mcp`
- 图谱：可选 Neo4j；不装则用 **SQLite 平替** + 本机 HTML 查看器

## 本地测试（D 盘）

```powershell
cd "D:\工作\项目\民政局\industry-graph-mcp"
$env:INDUSTRY_GRAPH_MCP_HOME="D:\industry-graph-mcp"
# 推荐使用 D 盘 Anaconda（避开系统 Python 3.14 的 pydantic DLL 问题）
D:\anaconda3\python.exe -m pip install -e ".[dev]"
D:\anaconda3\python.exe -m industry_graph_mcp setup -y --backend sqlite
D:\anaconda3\python.exe -m pytest -q
D:\anaconda3\python.exe tests\run_local_smoke.py
D:\anaconda3\python.exe -m industry_graph_mcp plan "我想调研一下广东的制造业"
```

别人体验（Cursor / Claude Code / Claude Desktop / Codex / WorkBuddy）见 `docs/体验指南.md`。全流程与流程图见 `docs/全流程.md`。

## 从你的服务器安装

见 `deploy-dist/README.md`。

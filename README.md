# Industry Graph MCP

面向全国各地区和产业的本地产业图谱与洞察 MCP。用户可以按地区和产业发起调研，通过 AI 客户端调用公开资料检索、企业档案补全、图谱查询和报告生成工具。调研数据、图谱和报告保存在本机。

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

别人体验，Windows 一条命令：

```powershell
irm https://raw.githubusercontent.com/192tt/industry-graph-mcp/master/deploy-dist/install.ps1 | iex
```

说明见 `docs/体验指南.md`。全流程（含标准企业表与入库补全）见 `docs/全流程.md`。当前版本 **0.6.0**。

## 从你的服务器安装

见 `deploy-dist/README.md`。

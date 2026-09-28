# WorkBuddy / 桌面 Agent 接入

与 Cursor 相同：使用 **stdio** 本地 MCP。

1. 安装：

```powershell
powershell -ExecutionPolicy Bypass -File "D:\工作\项目\民政局\industry-graph-mcp\deploy-dist\install.ps1" -SourceDir "D:\工作\项目\民政局\industry-graph-mcp" -HomeDir "D:\industry-graph-mcp"
```

2. 在 WorkBuddy MCP 配置中添加：

```json
{
  "command": "D:\\anaconda3\\python.exe",
  "args": ["-m", "industry_graph_mcp", "mcp"],
  "env": {
    "INDUSTRY_GRAPH_MCP_HOME": "D:\\industry-graph-mcp"
  }
}
```

3. 将仓库内 `SKILL.md` 加入 Agent 技能/说明，便于一句话产业调研编排。

# ChatGPT 连接本机 Industry Graph MCP

ChatGPT 网页端不能直接启动本机 stdio 进程。用 **OpenAI Secure MCP Tunnel** 把本机 MCP 挂上去，数据和图谱仍在本机 `D:\industry-graph-mcp`。

## 步骤概要

1. 本机已安装本 MCP，并能运行：

```powershell
$env:INDUSTRY_GRAPH_MCP_HOME="D:\industry-graph-mcp"
D:\anaconda3\python.exe -m industry_graph_mcp mcp
```

2. 按 OpenAI 文档安装并登录 `tunnel-client`（Secure MCP Tunnel）。
3. 将 tunnel 指向本机 MCP 命令，例如：

```text
--mcp-command D:\anaconda3\python.exe --mcp-args "-m,industry_graph_mcp,mcp"
```

并设置环境变量 `INDUSTRY_GRAPH_MCP_HOME=D:\industry-graph-mcp`。

4. 在 ChatGPT / Responses API 中使用返回的 `tunnel_id`（或产品内的 MCP 连接入口）。

## 注意

- 图谱与报告仍写在用户电脑 D 盘，不会上传到你的业务服务器。
- 长调研由 ChatGPT 多轮调用工具完成；勿做成单次超长阻塞。

官方文档入口：https://developers.openai.com/api/docs/guides/secure-mcp-tunnels

# 分发包说明（放到你的服务器静态目录）

将本仓库打成 `package.zip` 后上传到：

`https://YOUR_SERVER/industry-graph-mcp/package.zip`

并同时托管：

- `install.ps1`（Windows）
- `install.sh`（macOS/Linux）

用户安装（在线）：

```powershell
# 先把 DistBaseUrl 改成你的服务器
irm https://YOUR_SERVER/industry-graph-mcp/install.ps1 | iex
```

本地测试（不经过服务器，全部在 D:）：

```powershell
cd "D:\工作\项目\民政局\industry-graph-mcp"
powershell -ExecutionPolicy Bypass -File .\deploy-dist\install.ps1 -SourceDir (Get-Location).Path -HomeDir "D:\industry-graph-mcp" -Backend sqlite
```

服务器只负责分发安装包，不跑模型、不做采集。

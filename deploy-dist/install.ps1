# Industry Graph MCP — one-command install (Windows)
# Market pattern: one line, like `npx -y` / `irm ... | iex`.
#
#   irm https://raw.githubusercontent.com/192tt/industry-graph-mcp/master/deploy-dist/install.ps1 | iex
#
# Installs the package, creates the local data dir, and writes MCP config
# for whichever of Cursor / Claude Desktop / Claude Code / Codex is present.

param(
  [string]$SourceDir = "",
  [string]$RepoUrl = "https://github.com/192tt/industry-graph-mcp.git",
  [string]$HomeDir = "",
  [string]$Backend = "sqlite",
  [string]$Python = ""
)

$ErrorActionPreference = "Stop"

function Find-Python {
  param([string]$Preferred)
  if ($Preferred -and (Test-Path $Preferred)) { return $Preferred }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    $exe = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
    if ($exe) { return "$exe".Trim() }
    $exe = & py -3.10 -c "import sys; print(sys.executable)" 2>$null
    if ($exe) { return "$exe".Trim() }
  }
  foreach ($name in @("python", "python3")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
  }
  foreach ($candidate in @(
      "D:\anaconda3\python.exe",
      "$env:USERPROFILE\anaconda3\python.exe",
      "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
    )) {
    if (Test-Path $candidate) { return $candidate }
  }
  throw "Need Python 3.10 or 3.11 on PATH (py -3.11)."
}

function Find-Git {
  $cmd = Get-Command git -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  if (Test-Path "D:\Git\cmd\git.exe") { return "D:\Git\cmd\git.exe" }
  throw "Need git to clone the repo."
}

function Merge-McpJson {
  param([string]$Path, [object]$Server)
  $dir = Split-Path $Path -Parent
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  if (Test-Path $Path) {
    $existing = Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json
  } else {
    $existing = [pscustomobject]@{ mcpServers = [pscustomobject]@{} }
  }
  if (-not $existing.mcpServers) {
    $existing | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{})
  }
  $existing.mcpServers | Add-Member -NotePropertyName "industry-graph-mcp" -NotePropertyValue $Server -Force
  ($existing | ConvertTo-Json -Depth 8) | Set-Content -Path $Path -Encoding UTF8
  Write-Host "Wrote $Path"
}

if (-not $HomeDir) {
  if (Test-Path "D:\") { $HomeDir = "D:\industry-graph-mcp" }
  else { $HomeDir = Join-Path $env:USERPROFILE "industry-graph-mcp" }
}

$Python = Find-Python $Python
Write-Host "=== Industry Graph MCP ==="
Write-Host "Python=$Python"
Write-Host "HomeDir=$HomeDir"

New-Item -ItemType Directory -Force -Path $HomeDir, "$HomeDir\data", "$HomeDir\reports", "$HomeDir\cache" | Out-Null
$env:INDUSTRY_GRAPH_MCP_HOME = $HomeDir

if (-not $SourceDir) {
  $git = Find-Git
  $SourceDir = Join-Path $HomeDir "src\industry-graph-mcp"
  if (Test-Path (Join-Path $SourceDir ".git")) {
    Write-Host "Updating $SourceDir"
    & $git -C $SourceDir pull --ff-only
  } else {
    Write-Host "Cloning $RepoUrl"
    New-Item -ItemType Directory -Force -Path (Split-Path $SourceDir -Parent) | Out-Null
    & $git clone --depth 1 $RepoUrl $SourceDir
  }
}

Write-Host "Installing from $SourceDir"
& $Python -m pip install -e $SourceDir
& $Python -m industry_graph_mcp setup -y --backend $Backend

$server = [pscustomobject]@{
  command = $Python
  args    = @("-m", "industry_graph_mcp", "mcp")
  env     = [pscustomobject]@{ INDUSTRY_GRAPH_MCP_HOME = $HomeDir }
}

Merge-McpJson (Join-Path $env:USERPROFILE ".cursor\mcp.json") $server

$claudeDesktop = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"
if (Test-Path (Split-Path $claudeDesktop -Parent)) {
  Merge-McpJson $claudeDesktop $server
}

$claude = Get-Command claude -ErrorAction SilentlyContinue
if ($claude) {
  & claude mcp add industry-graph-mcp --env "INDUSTRY_GRAPH_MCP_HOME=$HomeDir" -- $Python -m industry_graph_mcp mcp
  Write-Host "Registered Claude Code via claude mcp add"
}

$codexDir = Join-Path $env:USERPROFILE ".codex"
if (Test-Path $codexDir) {
  $toml = Join-Path $codexDir "config.toml"
  $pyToml = $Python -replace '\\', '/'
  $homeToml = $HomeDir -replace '\\', '/'
  $block = @"

[mcp_servers.industry-graph-mcp]
command = "$pyToml"
args = ["-m", "industry_graph_mcp", "mcp"]

[mcp_servers.industry-graph-mcp.env]
INDUSTRY_GRAPH_MCP_HOME = "$homeToml"
"@
  if (-not (Test-Path $toml) -or -not (Select-String -Path $toml -Pattern "industry-graph-mcp" -Quiet)) {
    Add-Content -Path $toml -Value $block -Encoding UTF8
    Write-Host "Wrote $toml"
  } else {
    Write-Host "Codex already has industry-graph-mcp"
  }
}

$skillSrc = Join-Path $SourceDir "SKILL.md"
if (Test-Path $skillSrc) {
  Copy-Item $skillSrc (Join-Path $HomeDir "SKILL.md") -Force
}

Write-Host ""
Write-Host "Done. Restart the client (or reload MCP), then say:"
Write-Host "调研杭州科技企业，企业尽量多，最后出政策解读和产业洞察报告。"
Write-Host "Data stays on this machine: $HomeDir"

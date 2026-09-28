# Industry Graph MCP — local install from YOUR distribution server
# Usage (on user machine):
#   irm https://YOUR_SERVER/industry-graph-mcp/install.ps1 | iex
# Or offline from D: repo:
#   powershell -ExecutionPolicy Bypass -File .\deploy-dist\install.ps1 -SourceDir "D:\工作\项目\民政局\industry-graph-mcp"

param(
  [string]$SourceDir = "",
  [string]$DistBaseUrl = "https://YOUR_SERVER/industry-graph-mcp",
  [string]$HomeDir = "D:\industry-graph-mcp",
  [string]$Backend = "sqlite",
  [string]$Python = "D:\anaconda3\python.exe"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Industry Graph MCP Installer (D: data root) ==="
Write-Host "HomeDir=$HomeDir Backend=$Backend"

New-Item -ItemType Directory -Force -Path $HomeDir, "$HomeDir\data", "$HomeDir\reports", "$HomeDir\cache", "$HomeDir\dist" | Out-Null
$env:INDUSTRY_GRAPH_MCP_HOME = $HomeDir

if (-not $SourceDir) {
  $zipPath = Join-Path $HomeDir "dist\package.zip"
  $url = "$DistBaseUrl/package.zip"
  Write-Host "Downloading $url ..."
  try {
    Invoke-WebRequest -Uri $url -OutFile $zipPath
    $extract = Join-Path $HomeDir "dist\src"
    if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
    Expand-Archive -Path $zipPath -DestinationPath $extract -Force
    $SourceDir = Get-ChildItem $extract -Directory | Select-Object -First 1 -ExpandProperty FullName
    if (-not $SourceDir) { $SourceDir = $extract }
  } catch {
    Write-Host "Download failed. For local test, pass -SourceDir to the repo path."
    throw
  }
}

Write-Host "Installing from $SourceDir"
& $Python -m pip install -U pip
& $Python -m pip install -e $SourceDir

Write-Host "Running setup wizard (non-interactive, backend=$Backend)..."
& $Python -m industry_graph_mcp setup -y --backend $Backend

# Resolve python path for MCP config (escape backslashes for JSON)
if (-not (Test-Path $Python)) {
  $pyCmd = Get-Command python -ErrorAction SilentlyContinue
  if ($pyCmd) { $Python = $pyCmd.Source }
}
$pyJson = $Python -replace '\\', '\\'
$homeJson = $HomeDir -replace '\\', '\\'

$mcpObj = [ordered]@{
  mcpServers = [ordered]@{
    "industry-graph-mcp" = [ordered]@{
      command = $Python
      args = @("-m", "industry_graph_mcp", "mcp")
      env = [ordered]@{
        INDUSTRY_GRAPH_MCP_HOME = $HomeDir
      }
    }
  }
}
$mcpJson = $mcpObj | ConvertTo-Json -Depth 6

$cfgOut = Join-Path $HomeDir "cursor.mcp.json"
Set-Content -Path $cfgOut -Value $mcpJson -Encoding UTF8
Write-Host "Wrote MCP config example: $cfgOut"

# Auto-wire Cursor global MCP (merge if file already exists)
$cursorDir = Join-Path $env:USERPROFILE ".cursor"
New-Item -ItemType Directory -Force -Path $cursorDir | Out-Null
$cursorMcp = Join-Path $cursorDir "mcp.json"
if (Test-Path $cursorMcp) {
  try {
    $existing = Get-Content $cursorMcp -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $existing.mcpServers) { $existing | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) }
    $existing.mcpServers | Add-Member -NotePropertyName "industry-graph-mcp" -NotePropertyValue $mcpObj.mcpServers."industry-graph-mcp" -Force
    ($existing | ConvertTo-Json -Depth 8) | Set-Content -Path $cursorMcp -Encoding UTF8
    Write-Host "Merged into Cursor MCP: $cursorMcp"
  } catch {
    Set-Content -Path $cursorMcp -Value $mcpJson -Encoding UTF8
    Write-Host "Wrote Cursor MCP: $cursorMcp"
  }
} else {
  Set-Content -Path $cursorMcp -Value $mcpJson -Encoding UTF8
  Write-Host "Wrote Cursor MCP: $cursorMcp"
}

# Drop Skill next to data home for agents that scan it
$skillSrc = Join-Path $SourceDir "SKILL.md"
if (Test-Path $skillSrc) {
  Copy-Item $skillSrc (Join-Path $HomeDir "SKILL.md") -Force
}

Write-Host ""
Write-Host "Install done. Reload Cursor once, then just say: 我想调研一下广东的制造业"
Write-Host "(No need to mention MCP name — tools auto-trigger by intent.)"

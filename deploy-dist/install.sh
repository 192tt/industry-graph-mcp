#!/usr/bin/env bash
# Install Industry Graph MCP from YOUR distribution server (or local SourceDir).
# Data root defaults to /d/industry-graph-mcp when on Git Bash with D: mounted,
# otherwise override with INDUSTRY_GRAPH_MCP_HOME.
set -euo pipefail

DIST_BASE_URL="${DIST_BASE_URL:-https://YOUR_SERVER/industry-graph-mcp}"
HOME_DIR="${INDUSTRY_GRAPH_MCP_HOME:-/d/industry-graph-mcp}"
BACKEND="${BACKEND:-sqlite}"
SOURCE_DIR="${SOURCE_DIR:-}"
PYTHON="${PYTHON:-python3}"

echo "=== Industry Graph MCP Installer ==="
echo "HOME_DIR=$HOME_DIR BACKEND=$BACKEND"
mkdir -p "$HOME_DIR"/{data,reports,cache,dist}
export INDUSTRY_GRAPH_MCP_HOME="$HOME_DIR"

if [[ -z "$SOURCE_DIR" ]]; then
  ZIP="$HOME_DIR/dist/package.zip"
  echo "Downloading $DIST_BASE_URL/package.zip ..."
  curl -fsSL "$DIST_BASE_URL/package.zip" -o "$ZIP"
  rm -rf "$HOME_DIR/dist/src"
  mkdir -p "$HOME_DIR/dist/src"
  unzip -q "$ZIP" -d "$HOME_DIR/dist/src"
  SOURCE_DIR="$(find "$HOME_DIR/dist/src" -maxdepth 2 -type f -name pyproject.toml | head -n1 | xargs dirname)"
fi

"$PYTHON" -m pip install -U pip
"$PYTHON" -m pip install -e "$SOURCE_DIR"
"$PYTHON" -m industry_graph_mcp setup -y --backend "$BACKEND"

cat > "$HOME_DIR/cursor.mcp.json" <<EOF
{
  "mcpServers": {
    "industry-graph-mcp": {
      "command": "python",
      "args": ["-m", "industry_graph_mcp", "mcp"],
      "env": {
        "INDUSTRY_GRAPH_MCP_HOME": "$HOME_DIR"
      }
    }
  }
}
EOF

echo "Wrote $HOME_DIR/cursor.mcp.json"
echo "Install done."

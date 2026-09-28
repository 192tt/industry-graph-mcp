"""Report persistence helpers."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from industry_graph_mcp.config import reports_dir


def _safe_name(text: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", text.strip())
    return text[:80] or "report"


def save_report(
    title: str,
    content: str,
    scope: str = "default",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = reports_dir() / _safe_name(scope)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{ts}_{_safe_name(title)}.md"
    header = [
        f"# {title}",
        "",
        f"- 生成时间: {datetime.now().isoformat(timespec='seconds')}",
        f"- scope: {scope}",
        f"- 数据目录: {reports_dir()}",
    ]
    if meta:
        for k, v in meta.items():
            header.append(f"- {k}: {v}")
    header.append("")
    header.append("---")
    header.append("")
    body = "\n".join(header) + content.strip() + "\n"
    path.write_text(body, encoding="utf-8")
    return {"path": str(path), "scope": scope, "title": title, "bytes": path.stat().st_size}


def list_reports(scope: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    root = reports_dir()
    files: list[Path] = []
    if scope:
        d = root / _safe_name(scope)
        if d.exists():
            files = sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            files += sorted(d.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            # dedupe
            seen = set()
            uniq = []
            for p in files:
                if p in seen:
                    continue
                seen.add(p)
                uniq.append(p)
            files = uniq
    else:
        files = sorted(root.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in files[:limit]:
        out.append({"path": str(p), "name": p.name, "mtime": p.stat().st_mtime})
    return out

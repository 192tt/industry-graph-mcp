"""Render a knowledge-graph snapshot PNG for reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import math


def render_graph_snapshot(
    analytics: dict[str, Any],
    out_path: Path,
    max_nodes: int = 60,
) -> str | None:
    """
    Draw a readable subgraph snapshot with real edges.
    Keep: hub Region/Industry + top companies; pull incident edges from analytics.focus_edges.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "PingFang SC",
        "Noto Sans CJK SC",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    top = analytics.get("top_companies") or []
    hubs = analytics.get("hub_nodes") or []
    focus_edges = analytics.get("focus_edges") or analytics.get("sample_edges") or []
    all_nodes = analytics.get("sample_nodes") or []
    by_id = {n["id"]: n for n in all_nodes}

    keep: list[str] = []
    for h in hubs:
        keep.append(h["id"])
        by_id.setdefault(h["id"], h)
    for t in top[:40]:
        keep.append(t["id"])
        if t["id"] not in by_id:
            by_id[t["id"]] = {
                "id": t["id"],
                "labels": ["Company"],
                "properties": {"name": t["name"]},
            }
    # unique preserve order
    seen: set[str] = set()
    keep_u: list[str] = []
    for i in keep:
        if i not in seen:
            seen.add(i)
            keep_u.append(i)
    keep_u = keep_u[:max_nodes]
    keep_set = set(keep_u)

    links = []
    for e in focus_edges:
        s, t = e.get("source_id"), e.get("target_id")
        if s in keep_set and t in keep_set:
            links.append((s, t, e.get("rel_type") or ""))
        elif s in keep_set and t not in keep_set and len(keep_u) < max_nodes:
            # pull neighbor hub/company into view
            keep_u.append(t)
            keep_set.add(t)
            links.append((s, t, e.get("rel_type") or ""))
            by_id.setdefault(
                t,
                {"id": t, "labels": ["Entity"], "properties": {"name": t}},
            )
        elif t in keep_set and s not in keep_set and len(keep_u) < max_nodes:
            keep_u.append(s)
            keep_set.add(s)
            links.append((s, t, e.get("rel_type") or ""))
            by_id.setdefault(
                s,
                {"id": s, "labels": ["Entity"], "properties": {"name": s}},
            )

    if len(keep_u) < 2:
        return None

    hub_ids = [
        i
        for i in keep_u
        if "Industry" in (by_id.get(i, {}).get("labels") or [])
        or "Region" in (by_id.get(i, {}).get("labels") or [])
    ]
    company_ids = [i for i in keep_u if i not in hub_ids]

    pos: dict[str, tuple[float, float]] = {}
    for i, hid in enumerate(hub_ids or ["_c"]):
        ang = 2 * math.pi * i / max(len(hub_ids), 1) - math.pi / 2
        pos[hid] = (0.25 * math.cos(ang), 0.25 * math.sin(ang))
    for i, cid in enumerate(company_ids):
        ang = 2 * math.pi * i / max(len(company_ids), 1) - math.pi / 2
        pos[cid] = (math.cos(ang), math.sin(ang))

    fig, ax = plt.subplots(figsize=(11, 11))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        f"知识图谱抽样视图（{len(keep_u)} 节点 / {len(links)} 边）\nscope={analytics.get('scope')}"
    )

    for s, t, _ in links[:1200]:
        if s not in pos or t not in pos:
            continue
        x0, y0 = pos[s]
        x1, y1 = pos[t]
        ax.plot([x0, x1], [y0, y1], color="#94a3b8", linewidth=0.5, alpha=0.55, zorder=1)

    label_ids = set(hub_ids) | {t["id"] for t in top[:14]}
    for nid, (x, y) in pos.items():
        n = by_id.get(nid, {"id": nid, "labels": ["Company"], "properties": {}})
        labels = n.get("labels") or []
        if "Region" in labels:
            color, size = "#22c55e", 260
        elif "Industry" in labels:
            color, size = "#f59e0b", 240
        else:
            color, size = "#3d8bfd", 70
        ax.scatter([x], [y], s=size, c=color, zorder=2, edgecolors="white", linewidths=0.6)
        if nid in label_ids:
            name = (n.get("properties") or {}).get("name") or nid
            ax.text(x, y + 0.04, str(name)[:12], fontsize=8, ha="center", va="bottom")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor="white")
    plt.close(fig)
    return str(out_path)

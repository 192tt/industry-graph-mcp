"""Generate PNG charts for insight reports (matplotlib Agg)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _setup_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "PingFang SC",
        "Noto Sans CJK SC",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def _barh(path: Path, title: str, items: list[tuple[str, int]], xlabel: str = "数量") -> str | None:
    if not items:
        return None
    plt = _setup_matplotlib()
    labels = [k[:18] for k, _ in items[::-1]]
    values = [v for _, v in items[::-1]]
    fig, ax = plt.subplots(figsize=(8, max(3.5, 0.35 * len(labels) + 1)))
    ax.barh(labels, values, color="#3d8bfd")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return str(path)


def _pie(path: Path, title: str, items: list[tuple[str, int]]) -> str | None:
    if not items:
        return None
    plt = _setup_matplotlib()
    # Drop tiny slices that cause label pile-up; group into 其他
    total = sum(v for _, v in items) or 1
    major, other = [], 0
    for k, v in items:
        if v / total < 0.02 and k != items[0][0]:
            other += v
        else:
            major.append((k, v))
    if other:
        major.append(("其他/较小类", other))
    # If still one dominant >95%, prefer bar chart instead of pie
    if major and major[0][1] / total >= 0.95:
        return _barh(path, title + "（柱状，因过度集中）", items[:12])

    labels = [k[:12] for k, _ in major]
    values = [v for _, v in major]
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    wedges, texts, autotexts = ax.pie(
        values,
        labels=None,
        autopct=lambda p: f"{p:.1f}%" if p >= 3 else "",
        startangle=90,
        pctdistance=0.75,
    )
    ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1, 0.5), fontsize=9)
    ax.set_title(title)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def _without_generic(items: list[tuple[str, int]], generics: set[str]) -> list[tuple[str, int]]:
    return [(k, v) for k, v in items if k not in generics and v > 0]


def render_charts(analytics: dict[str, Any], assets_dir: Path) -> dict[str, str]:
    """Write chart PNGs; return map of chart_key -> path."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, str] = {}

    # Prefer inferred sub-industry for readable structure charts
    inferred = analytics.get("sub_industry_inferred") or analytics.get("sub_industry") or []
    raw = analytics.get("sub_industry") or []
    # Chart A: inferred distribution (exclude pure 科技（未细分） dominance by splitting view)
    readable = _without_generic(
        inferred,
        {"科技", "产业", "未标注细分", "科技（未细分）"},
    )
    if readable:
        p = _barh(
            assets_dir / "chart_sub_industry.png",
            "细分产业分布（名称规则推断，已排除笼统「科技」）",
            readable[:18],
        )
        if p:
            out["sub_industry"] = p
        # also keep residual count note chart
        residual = sum(v for k, v in inferred if k in {"科技", "科技（未细分）", "未标注细分", "产业"})
        if residual:
            p2 = _barh(
                assets_dir / "chart_sub_industry_residual.png",
                "仍为笼统「科技/未细分」的企业量（待补字段）",
                [("科技/未细分", residual), ("已推断细分", sum(v for _, v in readable))],
            )
            if p2:
                out["sub_industry_residual"] = p2
    elif raw:
        p = _barh(assets_dir / "chart_sub_industry.png", "细分产业分布（样本内原始字段）", raw[:18])
        if p:
            out["sub_industry"] = p

    roles = analytics.get("role_inferred") or analytics.get("role") or []
    labeled_roles = _without_generic(roles, {"未标注角色"})
    if labeled_roles:
        p = _pie(
            assets_dir / "chart_role.png",
            f"企业角色分布（规则补全；未标注 {dict(roles).get('未标注角色', 0)} 家另计）",
            labeled_roles,
        )
        if p:
            out["role"] = p
    elif roles:
        p = _barh(assets_dir / "chart_role.png", "企业角色分布（样本内）", roles[:12])
        if p:
            out["role"] = p

    p = _barh(
        assets_dir / "chart_district.png",
        "区县分布（仅统计已填区县字段的企业）",
        analytics.get("district") or [],
    )
    if p:
        out["district"] = p

    p = _barh(
        assets_dir / "chart_rel_types.png",
        "关系类型分布",
        analytics.get("rel_types") or [],
    )
    if p:
        out["rel_types"] = p

    tops = analytics.get("top_companies") or []
    if tops:
        items = [(t["name"][:16], int(t.get("degree") or 0)) for t in tops[:15]]
        items = [x for x in items if x[1] > 0] or [(t["name"][:16], 1) for t in tops[:15]]
        p = _barh(
            assets_dir / "chart_top_degree.png",
            "图谱连接度 Top 企业（样本内）",
            items,
        )
        if p:
            out["top_degree"] = p

    return out

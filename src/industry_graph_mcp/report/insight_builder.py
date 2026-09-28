"""Build policy-interpretation + industry-insight reports (Markdown primary)."""

from __future__ import annotations

import html
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from industry_graph_mcp.config import data_dir, reports_dir
from industry_graph_mcp.report.analytics import analyze_scope
from industry_graph_mcp.report.charts import render_charts
from industry_graph_mcp.report.graph_image import render_graph_snapshot


def _safe(text: str) -> str:
    import re

    text = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", (text or "").strip())
    return text[:80] or "report"


def _img_md(rel: str, caption: str) -> str:
    return f"![{caption}]({rel})\n\n*{caption}*\n"


def _mermaid_chain(region: str, industry: str, subs: list[tuple[str, int]]) -> str:
    top = subs[:6] if subs else [("细分赛道", 0)]
    lines = [
        "```mermaid",
        "flowchart LR",
        f"  R[{region}] --> I[{industry}产业]",
    ]
    for i, (name, cnt) in enumerate(top):
        lines.append(f"  I --> S{i}[{name}·{cnt}家]")
    lines.append("```")
    return "\n".join(lines)


def _generic_subs() -> set[str]:
    return {"科技", "产业", "未标注细分", "科技（未细分）", "产业（未细分）"}


def _readable_subs(analytics: dict[str, Any]) -> list[tuple[str, int]]:
    subs = analytics.get("sub_industry_inferred") or analytics.get("sub_industry") or []
    return [(k, v) for k, v in subs if k not in _generic_subs()]


def _load_policies(
    region: str,
    industry: str,
    policies: list[dict[str, Any]] | None,
    include_policies: bool,
    policy_num: int,
) -> list[dict[str, Any]]:
    if policies is not None:
        return list(policies)
    if not include_policies:
        return []
    try:
        from industry_graph_mcp.sources.policy import search_policies

        return search_policies(region, industry, num=policy_num)
    except Exception as exc:  # noqa: BLE001
        return [{"title": "政策检索失败", "snippet": str(exc), "error": True}]


def _exec_summary(
    analytics: dict[str, Any],
    region: str,
    industry: str,
    policies: list[dict[str, Any]],
) -> list[str]:
    subs_readable = _readable_subs(analytics)
    top = analytics.get("top_companies") or []
    roles = analytics.get("role_inferred") or analytics.get("role") or []
    policy_hits = [p for p in policies if isinstance(p, dict) and not p.get("error")]
    bullets = [
        f"**对象**: {region} · {industry}（scope=`{analytics.get('scope')}`）",
        f"**样本**: 公开源企业 **{analytics.get('companies')}** 家（非工商全量）；关系 {analytics.get('edges_total')}",
    ]
    if policy_hits:
        titles = "；".join((p.get("title") or "")[:40] for p in policy_hits[:3] if p.get("title"))
        bullets.append(f"**政策线索（公开检索 Top）**: {titles or '见正文政策清单'}")
    else:
        bullets.append("**政策线索**: 本轮未检索到可用政策条目（可手工传入 policies_json）")
    if subs_readable:
        top3 = "、".join(f"{k}({v})" for k, v in subs_readable[:3])
        bullets.append(f"**产业结构观察**: 细分靠前为 {top3}")
    if roles:
        bullets.append("**主体角色**: " + "、".join(f"{k} {v}家" for k, v in roles[:4]))
    if top:
        bullets.append("**代表企业**: " + "、".join(t["name"] for t in top[:5]))
    bullets.append(
        "**结论导向**: 政策红利应优先落到样本内已集聚的细分赛道与高连接度主体；"
        "仍「未细分」主体需用官方名录补分类后再精准匹配政策工具"
    )
    return bullets


def _policy_overview_md(policies: list[dict[str, Any]], region: str, industry: str) -> list[str]:
    lines = [
        "## 一、政策概述",
        "",
        f"本节汇总 **{region}·{industry}** 相关公开政策线索（优先 gov.cn 检索）。"
        "条目为检索命中摘要，**不等于**完整政策文本库。",
        "",
    ]
    hits = [p for p in policies if isinstance(p, dict) and not p.get("error")]
    if not hits:
        lines += [
            "| 字段 | 内容 |",
            "|---|---|",
            "| 发文机关 | （待补） |",
            "| 文件名称 | （本轮无公开检索命中 / 未传入 policies_json） |",
            "| 发布日期 | （待补） |",
            "| 政策类型 | 产业促进 / 高新技术 / 区域配套（待判定） |",
            "",
            "> 可在调用 `generate_insight_report` 时传入 `policies_json`，或先跑 `search_policies` 再写入。",
            "",
        ]
        return lines

    lines += [
        "| # | 标题 | 来源/链接 | 摘要 |",
        "|---|---|---|---|",
    ]
    for i, p in enumerate(hits[:12], 1):
        title = str(p.get("title") or "（无标题）").replace("|", "/")
        href = str(p.get("href") or p.get("url") or "")
        link = f"[链接]({href})" if href else "—"
        snip = str(p.get("body") or p.get("snippet") or "")[:120].replace("|", "/").replace("\n", " ")
        lines.append(f"| {i} | {title} | {link} | {snip} |")
    lines.append("")
    lines.append(
        f"- **检索口径**: 公开网页检索（约 {len(hits)} 条展示）；"
        "正式引用请核对原文发文机关、文号与效力。"
    )
    lines.append("")
    return lines


def _policy_background_md(region: str, industry: str, narrative: str) -> list[str]:
    lines = [
        "## 二、政策背景与意图",
        "",
        "### （一）出台背景与动因（框架）",
        f"- 区域经济与产业升级背景下，{region}围绕 **{industry}** 相关赛道持续出台支持与规范类文件。",
        "- 公开检索可见：高新技术认定、数字经济/智能制造、专精特新、园区与基金等工具并存。",
        "- **本报告定位**: 用本地图谱样本回答「政策可能落到哪些细分与主体」，而非替代官方政策汇编。",
        "",
        "### （二）与既有政策关系（解读提示）",
        "- 宜区分：国家顶层规划 → 省级实施意见 → 市级细则/名单 → 园区招商政策。",
        "- 解读时关注：**目标产业、政策工具、资格条件、考核监督、地方适配**（政策卡片化思路）。",
        "",
        "### （三）政策意图（Why）",
        f"- 做强 {region} {industry} 相关创新主体与产业链配套；",
        "- 用名单、基金、空间、研发支持等工具降低关键环节成本、提高集聚度。",
        "",
    ]
    if narrative.strip():
        lines += ["### 补充叙事（人工/编排输入）", "", narrative.strip(), ""]
    return lines


def _policy_core_md(policies: list[dict[str, Any]]) -> list[str]:
    hits = [p for p in policies if isinstance(p, dict) and not p.get("error")]
    lines = [
        "## 三、政策核心内容（What）",
        "",
        "按国内产业政策解读惯例，拆为措施 / 目标 / 支持 / 约束四块。"
        "下列为基于公开摘要的**结构化提纲**，细则以原文为准。",
        "",
        "### （一）主要措施（工具箱）",
        "- 供给类：研发支持、人才、土地/空间、基建与算力等要素保障",
        "- 需求类：首购首用、示范应用、政府采购、场景开放",
        "- 金融类：产业基金、信贷贴息、担保、上市培育",
        "- 准入与监管：认定目录、标准规范、安全合规",
        "- 供应链/集群：配套招商、产业链协同、园区载体",
        "",
        "### （二）目标指标（常见表述）",
        "- 主体培育：高新技术企业、专精特新、独角兽/拟上市数量",
        "- 产业规模：营收、增加值、固定资产投资",
        "- 创新：研发投入强度、专利/标准、重点实验室",
        "",
        "### （三）支持政策（红利识别提示）",
        "- 认定奖励、税优、租金/用能优惠、项目补贴、场景试点资格",
        "- **匹配建议**: 对照后文章节「样本内细分与代表企业」做资格初筛",
        "",
        "### （四）约束与考核",
        "- 环保、数据安全、反垄断、统计与绩效评估、退出与清退机制",
        "",
    ]
    if hits:
        lines.append("### （五）本轮检索条目要点摘录")
        lines.append("")
        for p in hits[:6]:
            title = p.get("title") or "（无标题）"
            snip = str(p.get("body") or p.get("snippet") or "").strip()[:200]
            lines.append(f"- **{title}**: {snip or '（无摘要，请打开链接阅读原文）'}")
        lines.append("")
    return lines


def _industry_panorama_md(
    analytics: dict[str, Any],
    region: str,
    industry: str,
    charts: dict[str, str],
    graph_png: str | None,
    assets: Path,
) -> list[str]:
    lines = [
        "## 四、区域产业样本全景（产业分析）",
        "",
        "本节融合行业研究报告中的「产业链/细分结构 + 竞争主体」模块，"
        "数据来自本地知识图谱公开样本。",
        "",
        "### （一）样本规模",
        "",
        "| 指标 | 数值 |",
        "|---|---|",
        f"| 企业数 | {analytics['companies']} |",
        f"| 节点总数 | {analytics['nodes_total']} |",
        f"| 关系数 | {analytics['edges_total']} |",
        f"| 产业/细分枢纽节点 | {analytics['industry_nodes']} |",
        f"| 地区节点 | {analytics['region_nodes']} |",
        "",
    ]
    for key, caption in [
        ("sub_industry", "细分产业分布"),
        ("role", "企业角色分布"),
        ("district", "区县分布"),
        ("rel_types", "关系类型分布"),
        ("top_degree", "连接度 Top 企业"),
    ]:
        if key in charts:
            lines.append(_img_md(f"assets/{Path(charts[key]).name}", caption))

    lines += [
        "### （二）产业结构示意（样本内）",
        "",
        "下图为基于样本细分统计的**示意性**结构，非官方标准产业链定义"
        "（参考地方产业链图谱构建思路：节点 + 上下游/隶属关系）。",
        "",
        _mermaid_chain(
            region,
            industry,
            analytics.get("sub_industry_inferred") or analytics.get("sub_industry") or [],
        ),
        "",
    ]
    if "sub_industry_residual" in charts:
        lines.append(_img_md("assets/chart_sub_industry_residual.png", "笼统标签 vs 已推断细分"))
        lines.append("")

    lines += [
        "### （三）知识图谱抽样视图",
        "",
        "大规模图谱不宜整图塞进报告；以下为头部企业 + 产业/地区枢纽抽样。"
        f"完整交互：`{assets / 'graph_viewer.html'}`",
        "",
    ]
    if graph_png:
        lines.append(_img_md("assets/knowledge_graph.png", "知识图谱抽样视图"))
    lines.append("")
    return lines


def _impact_md(analytics: dict[str, Any], region: str, industry: str) -> list[str]:
    subs_readable = _readable_subs(analytics)
    residual = 0
    for k, v in analytics.get("sub_industry_inferred") or analytics.get("sub_industry") or []:
        if k in _generic_subs():
            residual += v
    lines = [
        "## 五、影响分析（政策 × 产业样本）",
        "",
        "### （一）对行业的影响",
        f"- 政策工具若投向认定、基金与场景，将强化 {region} {industry} "
        "在软件信息、生物医药、互联网等**已露出集聚**的细分（见样本统计）。",
        "- 对仍大量「未细分」主体，政策精准度受限，易出现「广撒网、弱匹配」。",
        "",
        "### （二）对企业的影响",
        "- **龙头/骨干/独角兽**: 更易对接重大场景、基金与标准制定；关注合规与考核。",
        "- **高新技术企业主体**: 适合认定续期、研发加计、专精特新梯度培育。",
        "- **拟上市/专精特新（若名录并入）**: 对接口岸政策与上市培育工具。",
        "",
        "### （三）政策红利识别（对照样本）",
        "",
    ]
    if subs_readable:
        lines.append("| 样本内细分（推断） | 企业数 | 红利匹配提示 |")
        lines.append("|---|---|---|")
        for k, v in subs_readable[:10]:
            tip = "研发/场景/基金类工具优先" if v >= 50 else "结合区县与认定名录精筛"
            lines.append(f"| {k} | {v} | {tip} |")
        lines.append("")
    if residual:
        lines.append(
            f"- 仍有约 **{residual}** 家停留在笼统「科技/未细分」，"
            "红利识别前应补官方分类或经营范围。"
        )
        lines.append("")
    if analytics.get("district"):
        lines.append("### （四）空间落地提示（有区县字段时）")
        lines.append("")
        for k, v in (analytics.get("district") or [])[:8]:
            lines.append(f"- {k}: {v} 家（园区/区级政策可优先对齐）")
        lines.append("")
    return lines


def _companies_md(analytics: dict[str, Any], max_table: int) -> list[str]:
    lines = [
        "## 六、代表企业与赛道速览",
        "",
        "下列企业按图谱连接度与角色优先级展示，**连接度 ≠ 市占率**。",
        "",
        "| 企业 | 细分 | 角色 | 区县 | 连接度 |",
        "|---|---|---|---|---|",
    ]
    for t in (analytics.get("top_companies") or [])[:max_table]:
        lines.append(
            f"| {t['name']} | {t.get('sub_industry', '')} | {t.get('role', '')} | "
            f"{t.get('district', '')} | {t.get('degree', 0)} |"
        )
    lines.append("")
    return lines


def _advice_md(region: str, industry: str, analytics: dict[str, Any]) -> list[str]:
    subs_readable = _readable_subs(analytics)
    focus = "、".join(k for k, _ in subs_readable[:3]) or industry
    return [
        "## 七、应对建议",
        "",
        "### （一）战略调整建议（政府 / 园区）",
        f"- 以 **{focus}** 等样本集聚赛道作为政策工具投放与招商地图的主轴。",
        "- 把「高新名单扩面」升级为「赛道×区县×政策工具」三维台账。",
        "- 对未细分主体开展分类补录（专精特新、区县高企、招投标中标人）。",
        "",
        "### （二）具体行动建议（企业）",
        "- 对照认定条件与场景清单，准备研发费用、知识产权、标准与示范案例材料。",
        "- 龙头与链主企业主动申报重大场景；中小企业切入配套与专精特新梯度。",
        "- 关注数据安全、出口管制与行业准入等约束条款，避免红利与合规对冲。",
        "",
        "### （三）风险提示",
        "- 公开源偏差：上榜企业被高估，大量未披露主体缺失。",
        "- 名称关键词推断的细分/角色 **≠** 工商或工信分类。",
        "- 检索到的政策摘要可能过期或非现行有效，落地前必须核对原文。",
        "- 图谱连接度不能直接当作市场份额或产业链掌控力。",
        "",
        "### （四）下一步工作清单",
        f"- 并入 {region} 专精特新 / 区县名录，降低「未细分」占比。",
        "- 对 Top 企业公开尽调补经营范围，回写 sub_industry。",
        "- 将政策原文拆成「政策卡片」（工具、条件、考核）并挂接到赛道节点。",
        "- 需要精美截图时，在 `graph_viewer.html` 中手工截取替换知识图谱图。",
        "",
    ]


def _appendix_md(
    folder: Path,
    enrich_meta: dict[str, Any] | None,
    policies: list[dict[str, Any]],
) -> list[str]:
    hits = [p for p in policies if isinstance(p, dict) and not p.get("error")]
    lines = [
        "## 附录",
        "",
        "### A. 方法与模板依据",
        "1. 国内产业政策解读模板：概述 → 背景 → 核心内容 → 影响 → 建议 → 附录",
        "2. 融合产业分析：样本结构统计、细分示意、知识图谱、代表企业（行业研究常用模块）",
        "3. 参考实践：政策卡片化（工具/条件/考核）、产业链节点关系、招商调研「政策—产业—企业」闭环",
        "4. 技术路径：公开检索政策线索 + GraphStore 统计 + matplotlib / 抽样图谱 + Markdown 主交付",
        "",
        "### B. 数据口径",
        f"- 数据目录：`{data_dir()}`",
        f"- 本报告目录：`{folder}`",
        "- 公开检索样本 ≠ 工商登记全量；推断字段需人工复核。",
        "",
    ]
    if enrich_meta:
        lines.append(
            f"- 字段补全：更新 {enrich_meta.get('updated')} / {enrich_meta.get('companies')} 家"
            "（名称关键词推断）"
        )
        lines.append("")
    lines.append("### C. 相关政策清单（本轮检索）")
    lines.append("")
    if hits:
        for p in hits:
            href = p.get("href") or p.get("url") or ""
            title = p.get("title") or href or "（条目）"
            lines.append(f"- [{title}]({href})" if href else f"- {title}")
    else:
        lines.append("- （空）")
    lines.append("")
    return lines


def build_insight_report(
    store,
    scope: str,
    title: str | None = None,
    region: str = "",
    industry: str = "",
    narrative: str = "",
    max_table: int = 30,
    open_html: bool = False,
    auto_enrich: bool = True,
    include_policies: bool = True,
    policy_num: int = 8,
    policies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Generate Markdown-primary report:
    国内产业政策解读模板 + 区域产业样本洞察（统计图/图谱/企业表）。
    """
    if not region or not industry:
        if "_" in scope:
            parts = scope.split("_", 1)
            region = region or parts[0]
            industry = industry or parts[1]
        else:
            region = region or scope
            industry = industry or "产业"

    enrich_meta: dict[str, Any] | None = None
    if auto_enrich:
        from industry_graph_mcp.enrich import enrich_scope_companies

        enrich_meta = enrich_scope_companies(
            store,
            scope=scope,
            write_back=True,
            add_sub_edges=False,
            default_region=region,
            default_industry=industry or "科技",
        )

    analytics = analyze_scope(store, scope, top_n=max(max_table, 30))
    policy_list = _load_policies(region, industry, policies, include_policies, policy_num)

    title = title or f"{region}{industry}产业政策解读与产业洞察报告"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = reports_dir() / _safe(scope) / f"{ts}_insight"
    assets = folder / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    charts = render_charts(analytics, assets)
    graph_png = render_graph_snapshot(analytics, assets / "knowledge_graph.png", max_nodes=80)

    viewer_src = Path(__file__).resolve().parents[1] / "graph" / "viewer" / "graph_viewer.html"
    export = {
        "backend": getattr(store, "backend_name", "unknown"),
        "scope": scope,
        "nodes": store.query_nodes(scope=scope, limit=5000),
        "edges": store.query_relations(scope=scope, limit=15000),
    }
    if len(export["nodes"]) > 800:
        keep_ids = {t["id"] for t in analytics.get("top_companies") or []}
        for n in export["nodes"]:
            if "Industry" in (n.get("labels") or []) or "Region" in (n.get("labels") or []):
                keep_ids.add(n["id"])
        trimmed_nodes = [n for n in export["nodes"] if n["id"] in keep_ids][:800]
        ids = {n["id"] for n in trimmed_nodes}
        trimmed_edges = [
            e
            for e in export["edges"]
            if e.get("source_id") in ids and e.get("target_id") in ids
        ][:3000]
        export = {**export, "nodes": trimmed_nodes, "edges": trimmed_edges, "trimmed": True}
    (assets / "graph_data.json").write_text(
        json.dumps(export, ensure_ascii=False), encoding="utf-8"
    )
    if viewer_src.exists():
        shutil.copy2(viewer_src, assets / "graph_viewer.html")

    md: list[str] = [
        f"# {title}",
        "",
        f"> 模板：国内**产业政策解读**（概述→背景→内容→影响→建议）"
        f" + **区域产业样本洞察**（结构图/图谱/企业）。",
        f"> 时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} ｜ scope=`{scope}` ｜ "
        f"后端={getattr(store, 'backend_name', '')}",
        "",
        "## 0. 执行摘要与口径",
        "",
        "- 公开名单/网页检索样本，**不等于**工商全量或付费企业库。",
        f"- 企业节点：{analytics['companies']}；总节点：{analytics['nodes_total']}；"
        f"关系：{analytics['edges_total']}",
        f"- 主交付物：本 Markdown；同目录 `index.html` / `assets/` 为附件。",
        "",
    ]
    for b in _exec_summary(analytics, region, industry, policy_list):
        md.append(f"- {b}")
    md.append("")

    md.extend(_policy_overview_md(policy_list, region, industry))
    md.extend(_policy_background_md(region, industry, narrative))
    md.extend(_policy_core_md(policy_list))
    md.extend(_industry_panorama_md(analytics, region, industry, charts, graph_png, assets))
    md.extend(_impact_md(analytics, region, industry))
    md.extend(_companies_md(analytics, max_table))
    md.extend(_advice_md(region, industry, analytics))
    md.extend(_appendix_md(folder, enrich_meta, policy_list))

    md_path = folder / f"{_safe(title)}.md"
    md_text = "\n".join(md) + "\n"
    md_path.write_text(md_text, encoding="utf-8")
    (folder / "REPORT.md").write_text(md_text, encoding="utf-8")

    # HTML companion (compact)
    html_parts = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'/>",
        f"<title>{html.escape(title)}</title>",
        "<style>",
        "body{font-family:'Segoe UI','Microsoft YaHei',sans-serif;max-width:920px;margin:24px auto;"
        "padding:0 16px;line-height:1.6;color:#0f172a;background:#f8fafc}",
        "h1,h2,h3{color:#0f172a} img{max-width:100%;border:1px solid #e2e8f0;border-radius:8px;background:#fff}",
        "table{border-collapse:collapse;width:100%;background:#fff} th,td{border:1px solid #e2e8f0;padding:8px;font-size:14px}",
        "blockquote{background:#eff6ff;border-left:4px solid #3d8bfd;padding:8px 12px;margin:12px 0}",
        ".cap{color:#64748b;font-size:13px;margin-top:4px}",
        "</style></head><body>",
        f"<h1>{html.escape(title)}</h1>",
        f"<blockquote>政策解读 + 产业洞察 ｜ scope={html.escape(scope)} ｜ "
        f"企业 {analytics['companies']} ｜ 公开样本非全量</blockquote>",
        "<h2>执行摘要</h2><ul>",
    ]
    for b in _exec_summary(analytics, region, industry, policy_list):
        html_parts.append(f"<li>{html.escape(b)}</li>")
    html_parts.append("</ul><h2>统计图与图谱</h2>")
    for key, caption in [
        ("sub_industry", "细分产业"),
        ("role", "角色"),
        ("district", "区县"),
        ("rel_types", "关系类型"),
        ("top_degree", "连接度 Top"),
    ]:
        if key in charts:
            name = Path(charts[key]).name
            html_parts.append(f"<img src='assets/{name}' alt='{html.escape(caption)}'/>")
            html_parts.append(f"<div class='cap'>{html.escape(caption)}</div>")
    if graph_png:
        html_parts.append("<img src='assets/knowledge_graph.png' alt='kg'/>")
        html_parts.append("<div class='cap'>知识图谱抽样；完整交互见 graph_viewer.html</div>")
    html_parts.append("<p><a href='assets/graph_viewer.html'>打开交互图谱</a></p>")
    html_parts.append("<h2>代表企业</h2><table><tr><th>企业</th><th>细分</th><th>角色</th><th>连接度</th></tr>")
    for t in (analytics.get("top_companies") or [])[:max_table]:
        html_parts.append(
            "<tr>"
            f"<td>{html.escape(str(t['name']))}</td>"
            f"<td>{html.escape(str(t.get('sub_industry') or ''))}</td>"
            f"<td>{html.escape(str(t.get('role') or ''))}</td>"
            f"<td>{t.get('degree', 0)}</td>"
            "</tr>"
        )
    html_parts.append("</table>")
    html_parts.append("<p>完整政策解读与建议见 Markdown 正文 REPORT.md。</p></body></html>")
    html_path = folder / "index.html"
    html_path.write_text("\n".join(html_parts), encoding="utf-8")

    (assets / "policies.json").write_text(
        json.dumps(policy_list, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    meta = {
        "folder": str(folder),
        "primary": "markdown",
        "template": "policy_interpretation_plus_industry_insight",
        "markdown": str(md_path),
        "report_md": str(folder / "REPORT.md"),
        "html": str(html_path),
        "assets": str(assets),
        "charts": charts,
        "graph_image": graph_png,
        "companies": analytics["companies"],
        "nodes": analytics["nodes_total"],
        "edges": analytics["edges_total"],
        "scope": scope,
        "title": title,
        "enrich": enrich_meta,
        "policies_count": len([p for p in policy_list if isinstance(p, dict) and not p.get("error")]),
    }
    (folder / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if open_html:
        import webbrowser

        webbrowser.open(html_path.as_uri())

    return meta

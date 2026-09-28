"""Enrich company fields (sub_industry / role) for bulk imports lacking taxonomy."""

from __future__ import annotations

import re
from typing import Any

# Longer / more specific keywords first
_SUB_RULES: list[tuple[str, str]] = [
    ("集成电路", "半导体"),
    ("微电子", "半导体"),
    ("晶圆", "半导体"),
    ("半导体", "半导体"),
    ("芯片", "半导体"),
    ("光电子", "光电/显示"),
    ("光电", "光电/显示"),
    ("显示", "光电/显示"),
    ("激光", "光电/光学"),
    ("光学", "光电/光学"),
    ("安防", "安防/视觉"),
    ("监控", "安防/视觉"),
    ("视觉", "安防/视觉"),
    ("机器人", "机器人/智能硬件"),
    ("无人机", "机器人/智能硬件"),
    ("智能硬件", "机器人/智能硬件"),
    ("生物医药", "生物医药"),
    ("基因", "生物医药"),
    ("制药", "生物医药"),
    ("医药", "生物医药"),
    ("医疗", "生物医药"),
    ("生物", "生物医药"),
    ("诊断", "生物医药"),
    ("金融科技", "金融科技"),
    ("支付", "金融科技"),
    ("证券", "金融IT"),
    ("银行", "金融IT"),
    ("区块链", "区块链"),
    ("云计算", "云计算/ICT"),
    ("大数据", "大数据/云计算"),
    ("物联网", "物联网"),
    ("传感", "物联网/传感"),
    ("电商", "电商/数字经济"),
    ("电子商务", "电商/数字经济"),
    ("互联网", "互联网/网络"),
    ("网络科技", "互联网/网络"),
    ("网络技术", "互联网/网络"),
    ("游戏", "游戏/互联网"),
    ("软件", "软件与信息服务"),
    ("信息科技", "软件与信息服务"),
    ("信息技术", "软件与信息服务"),
    ("信息", "软件与信息服务"),
    ("智能制造", "智能制造"),
    ("数控", "智能制造"),
    ("自动化", "工业自动化"),
    ("装备", "高端装备"),
    ("机电", "机电装备"),
    ("电气", "电气设备"),
    ("新材料", "新材料"),
    ("材料", "新材料"),
    ("新能源", "新能源"),
    ("光伏", "新能源"),
    ("电池", "新能源"),
    ("氢能", "新能源"),
    ("通信", "通信设备"),
    ("电子", "电子信息"),
    ("航空", "航空航天"),
    ("航天", "航空航天"),
    ("汽车", "汽车智能/出行"),
    ("环保", "节能环保"),
    ("节能", "节能环保"),
    ("检测", "检验检测"),
    ("仪器", "仪器仪表"),
    ("仪表", "仪器仪表"),
    ("化工", "精细化工"),
    ("存储", "存储/ICT"),
    ("数据", "大数据/云计算"),
    ("网络", "互联网/网络"),
    ("云", "云计算/ICT"),
]

_GENERIC_SUB = {"", "科技", "产业", "未标注细分", "科技（未细分）", "产业（未细分）"}

_ROLE_SEEDS: dict[str, str] = {
    "阿里巴巴": "龙头",
    "蚂蚁": "龙头",
    "网易": "龙头",
    "海康威视": "龙头",
    "大华": "龙头",
    "新华三": "龙头",
    "华三": "龙头",
    "士兰微": "龙头",
    "中控": "龙头",
    "同花顺": "龙头",
    "安恒": "龙头",
    "迪普": "骨干",
    "顺网": "骨干",
    "先临三维": "骨干",
    "群核": "新兴",
    "云深处": "新兴",
    "宇树": "独角兽",
    "深度求索": "独角兽",
    "趣链": "独角兽",
    "强脑": "新兴",
    "游戏科学": "新兴",
    "乒乓": "独角兽",
}

_BOM_NUM = re.compile(r"^[\ufeff\s]*(?:\d+[\.、\s]+)?")


def clean_company_name(name: str) -> str:
    name = (name or "").strip()
    name = _BOM_NUM.sub("", name).strip()
    return name


def infer_sub_industry(name: str, props: dict[str, Any] | None = None) -> str:
    props = props or {}
    explicit = str(props.get("sub_industry") or "").strip()
    if explicit and explicit not in _GENERIC_SUB:
        return explicit
    industry = str(props.get("industry") or "").strip()
    if industry and industry not in ("科技", "产业"):
        return industry
    text = f"{name}{props.get('note') or ''}{props.get('alias') or ''}"
    for kw, label in _SUB_RULES:
        if kw in text:
            return label
    if industry:
        return f"{industry}（未细分）"
    return "未标注细分"


def infer_role(name: str, props: dict[str, Any] | None = None) -> str:
    props = props or {}
    explicit = str(props.get("role") or "").strip()
    if explicit and explicit not in ("未标注角色", "未知", ""):
        return explicit
    for kw, role in _ROLE_SEEDS.items():
        if kw in name:
            return role
    src = str(props.get("source") or props.get("source_type") or "")
    if "拟上市" in src or props.get("ipo_pipeline"):
        return "拟上市"
    if "unicorn" in src.lower() or "独角兽" in src:
        return "独角兽"
    if "专精特新" in src:
        return "专精特新"
    if "hightech" in src.lower() or "高新" in src or "public_hightech" in src:
        return "高新技术企业"
    if props.get("industry") in ("科技", "数字经济") or "科技" in str(props.get("industry") or ""):
        return "高新技术企业"
    return "未标注角色"


def enrich_company_props(
    name: str,
    props: dict[str, Any] | None = None,
    default_region: str = "",
    default_industry: str = "科技",
) -> dict[str, Any]:
    """Fill sub_industry / role for bulk high-tech rows that only have region+industry."""
    name = clean_company_name(name)
    props = dict(props or {})
    props["name"] = name
    if default_region and not props.get("region"):
        props["region"] = default_region
    if not props.get("industry"):
        props["industry"] = default_industry
    props["sub_industry"] = infer_sub_industry(name, props)
    props["role"] = infer_role(name, props)
    props.setdefault("sub_industry_source", "name_keyword_infer")
    props.setdefault("role_source", "rule_infer")
    return props


def enrich_scope_companies(
    store,
    scope: str,
    write_back: bool = True,
    add_sub_edges: bool = True,
    default_region: str = "",
    default_industry: str = "科技",
    limit: int = 100000,
) -> dict[str, Any]:
    """
    Backfill sub_industry/role on existing Company nodes in a scope.
    Optionally add IN_SUB_INDUSTRY edges to Industry hubs for inferred segments.
    """
    nodes = store.query_nodes(label="Company", scope=scope, limit=limit)
    updated = 0
    edges_added = 0
    sub_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}

    existing_sub_edges: set[tuple[str, str]] = set()
    if add_sub_edges:
        for e in store.query_relations(scope=scope, rel_type="IN_SUB_INDUSTRY", limit=500000):
            existing_sub_edges.add((str(e.get("source_id") or ""), str(e.get("target_id") or "")))

    # Create hubs once
    hubs_ready: set[str] = set()

    for n in nodes:
        props = dict(n.get("properties") or {})
        name = clean_company_name(str(props.get("name") or n["id"]))
        before_sub = props.get("sub_industry")
        before_role = props.get("role")
        enriched = enrich_company_props(
            name, props, default_region=default_region, default_industry=default_industry
        )
        sub_counts[enriched["sub_industry"]] = sub_counts.get(enriched["sub_industry"], 0) + 1
        role_counts[enriched["role"]] = role_counts.get(enriched["role"], 0) + 1

        node_id = n["id"]
        if write_back and (
            before_sub != enriched["sub_industry"]
            or before_role != enriched["role"]
            or props.get("name") != name
        ):
            store.upsert_node(
                node_id,
                labels=n.get("labels") or ["Company"],
                properties={**enriched, "canonical_name": name} if node_id != name else enriched,
                scope=scope,
            )
            if node_id != name:
                # Prefer clean id as canonical company node for future joins
                store.upsert_node(
                    name,
                    labels=n.get("labels") or ["Company"],
                    properties=enriched,
                    scope=scope,
                )
            updated += 1

        if add_sub_edges:
            sub = enriched["sub_industry"]
            if sub and sub not in _GENERIC_SUB and "未细分" not in sub:
                hub_id = f"细分_{sub}"
                if hub_id not in hubs_ready:
                    store.upsert_node(
                        hub_id,
                        labels=["Industry"],
                        properties={"name": sub, "type": "细分产业"},
                        scope=scope,
                    )
                    hubs_ready.add(hub_id)
                src = name if (node_id == name or store.get_node(name, scope)) else node_id
                key = (src, hub_id)
                if key not in existing_sub_edges:
                    store.add_relation(
                        src,
                        hub_id,
                        "IN_SUB_INDUSTRY",
                        {"inferred": True},
                        scope=scope,
                    )
                    existing_sub_edges.add(key)
                    edges_added += 1

    return {
        "scope": scope,
        "companies": len(nodes),
        "updated": updated,
        "edges_added": edges_added,
        "write_back": write_back,
        "sub_industry_top": sorted(sub_counts.items(), key=lambda x: -x[1])[:20],
        "role_top": sorted(role_counts.items(), key=lambda x: -x[1])[:15],
    }

"""Canonical company fields — aligned with Beijing eldercare master CSV."""

from __future__ import annotations

from typing import Any

# Display / CSV column order (Chinese headers)
STANDARD_HEADERS: list[str] = [
    "序号",
    "企业名称",
    "联系电话",
    "统一社会信用代码",
    "法人",
    "成立日期",
    "注册资本(万)",
    "所属区县",
    "注册街道",
    "注册地址",
    "核心技术/产品/服务",
    "产业链",
    "细分小类",
    "所获专利",
    "单位资质",
    "获得荣誉",
    "企业风险",
    "分类理由",
    "数据来源",
    "筛选标记",
]

# Internal property keys mirror Chinese headers where possible
PROP_KEYS: list[str] = [
    "name",
    "phone",
    "credit_code",
    "legal_person",
    "establish_date",
    "registered_capital_wan",
    "district",
    "street",
    "address",
    "core_tech",
    "industry_chain",
    "sub_industry",
    "patents",
    "qualifications",
    "honors",
    "risk",
    "classify_reason",
    "source",
    "filter_tag",
]

# Map Chinese header -> internal property
HEADER_TO_PROP: dict[str, str] = {
    "企业名称": "name",
    "联系电话": "phone",
    "统一社会信用代码": "credit_code",
    "法人": "legal_person",
    "成立日期": "establish_date",
    "注册资本(万)": "registered_capital_wan",
    "所属区县": "district",
    "注册街道": "street",
    "注册地址": "address",
    "核心技术/产品/服务": "core_tech",
    "产业链": "industry_chain",
    "细分小类": "sub_industry",
    "所获专利": "patents",
    "单位资质": "qualifications",
    "获得荣誉": "honors",
    "企业风险": "risk",
    "分类理由": "classify_reason",
    "数据来源": "source",
    "筛选标记": "filter_tag",
}

PROP_TO_HEADER: dict[str, str] = {v: k for k, v in HEADER_TO_PROP.items()}

# Aliases from messy import / old English keys
ALIASES: dict[str, str] = {
    "企业名称": "name",
    "公司名称": "name",
    "name": "name",
    "联系电话": "phone",
    "电话": "phone",
    "phone": "phone",
    "tel": "phone",
    "统一社会信用代码": "credit_code",
    "信用代码": "credit_code",
    "credit_code": "credit_code",
    "uscc": "credit_code",
    "法人": "legal_person",
    "法定代表人": "legal_person",
    "legal_person": "legal_person",
    "成立日期": "establish_date",
    "成立时间": "establish_date",
    "establish_date": "establish_date",
    "注册资本(万)": "registered_capital_wan",
    "注册资本": "registered_capital_wan",
    "registered_capital_wan": "registered_capital_wan",
    "所属区县": "district",
    "区县": "district",
    "district": "district",
    "注册街道": "street",
    "街道": "street",
    "street": "street",
    "注册地址": "address",
    "地址": "address",
    "address": "address",
    "核心技术/产品/服务": "core_tech",
    "核心技术": "core_tech",
    "产品": "core_tech",
    "core_tech": "core_tech",
    "note": "core_tech",
    "产业链": "industry_chain",
    "industry_chain": "industry_chain",
    "细分小类": "sub_industry",
    "细分": "sub_industry",
    "sub_industry": "sub_industry",
    "所获专利": "patents",
    "专利": "patents",
    "patents": "patents",
    "role": "role",
    "单位资质": "qualifications",
    "资质": "qualifications",
    "qualifications": "qualifications",
    "获得荣誉": "honors",
    "荣誉": "honors",
    "honors": "honors",
    "企业风险": "risk",
    "风险": "risk",
    "risk": "risk",
    "分类理由": "classify_reason",
    "classify_reason": "classify_reason",
    "数据来源": "source",
    "source": "source",
    "筛选标记": "filter_tag",
    "filter_tag": "filter_tag",
}


def normalize_props(props: dict[str, Any] | None) -> dict[str, Any]:
    """Fold aliases into canonical internal keys; keep unknown keys."""
    out: dict[str, Any] = {}
    for k, v in (props or {}).items():
        if v in (None, ""):
            continue
        key = ALIASES.get(str(k).strip(), str(k).strip())
        if key in out and out[key]:
            continue
        out[key] = v
    return out


def props_to_csv_row(index: int, props: dict[str, Any]) -> dict[str, str]:
    """One company -> Chinese-header CSV row."""
    p = normalize_props(props)
    if not p.get("qualifications") and p.get("role"):
        p["qualifications"] = str(p["role"])
    if not p.get("industry_chain"):
        p["industry_chain"] = ""
    row: dict[str, str] = {"序号": str(index)}
    for header in STANDARD_HEADERS:
        if header == "序号":
            continue
        prop = HEADER_TO_PROP[header]
        val = p.get(prop)
        if val is None:
            val = ""
        row[header] = str(val).replace("\r", " ").replace("\n", " ").strip()
    return row


def missing_profile_fields(props: dict[str, Any] | None) -> list[str]:
    """Fields still empty (for enrichment targeting)."""
    p = normalize_props(props)
    need = [
        "phone",
        "credit_code",
        "legal_person",
        "establish_date",
        "registered_capital_wan",
        "district",
        "street",
        "address",
        "core_tech",
        "patents",
        "qualifications",
        "honors",
    ]
    return [k for k in need if not str(p.get(k) or "").strip()]

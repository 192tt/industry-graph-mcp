"""Public-web company profile enrichment (no paid enterprise DB)."""

from __future__ import annotations

import re
import time
from typing import Any

from industry_graph_mcp.enrich import clean_company_name, enrich_company_props, infer_role, infer_sub_industry
from industry_graph_mcp.schema import missing_profile_fields, normalize_props
from industry_graph_mcp.search_fetch import do_fetch, do_search

_CREDIT = re.compile(r"(?<![0-9A-Za-z])([0-9A-Z]{18})(?![0-9A-Za-z])")
_PHONE = re.compile(
    r"(?:电话|联系电话|Tel|TEL|手机|联系方式)[:：\s]*"
    r"((?:\+?86[-\s]?)?(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}))"
)
_PHONE_LOOSE = re.compile(r"(?<!\d)(1[3-9]\d{9}|0\d{2,3}-\d{7,8})(?!\d)")
_LEGAL = re.compile(r"(?:法定代表人|法人代表|法人)[:：\s]*([\u4e00-\u9fff·]{2,8})")
_DATE = re.compile(
    r"(?:成立日期|成立时间|注册日期|成立于)[:：\s]*"
    r"((?:19|20)\d{2}[年./\-]\d{1,2}(?:[月./\-]\d{1,2})?)"
)
_CAPITAL = re.compile(
    r"(?:注册资本|实缴资本)[:：\s]*([\d.,]+)\s*(?:万|万元|万人民币)?"
)
_ADDRESS = re.compile(
    r"(?:注册地址|住所|地址|办公地址)[:：\s]*"
    r"((?:[\u4e00-\u9fffA-Za-z0-9\-号楼室层单元]{8,80}))"
)
_DISTRICT = re.compile(
    r"(杭州|北京|上海|深圳|广州|南京|苏州|成都|武汉|西安|宁波|温州|嘉兴|湖州|绍兴|金华|"
    r"滨江|余杭|西湖|萧山|拱墅|上城|临平|钱塘|海淀|朝阳|浦东|南山|福田)"
    r"(?:区|市)?"
)
_PATENT = re.compile(r"(?:发明专利|实用新型|外观设计|专利)[^\n]{0,20}?(\d+)\s*项")
_HONOR = re.compile(
    r"(专精特新(?:小巨人)?|高新技术企业|独角兽|瞪羚|隐形冠军|科创板|拟上市|上市)"
)


def _first(pattern: re.Pattern[str], text: str) -> str:
    m = pattern.search(text or "")
    return m.group(1).strip() if m else ""


def _pick_district(text: str, region_hint: str = "") -> str:
    for m in _DISTRICT.finditer(text or ""):
        token = m.group(1)
        if token in ("滨江", "余杭", "西湖", "萧山", "拱墅", "上城", "临平", "钱塘"):
            return f"{token}区" if not token.endswith("区") else token
        if token in ("海淀", "朝阳"):
            return f"{token}区"
        if region_hint and token == region_hint.rstrip("市"):
            continue
    return ""


def extract_fields_from_text(text: str, company_name: str = "") -> dict[str, str]:
    """Regex extract public profile fields from page/snippet text."""
    blob = text or ""
    out: dict[str, str] = {}
    credit = _first(_CREDIT, blob)
    if credit and credit[0].isdigit():
        out["credit_code"] = credit
    phone = _first(_PHONE, blob) or _first(_PHONE_LOOSE, blob)
    if phone:
        out["phone"] = phone
    legal = _first(_LEGAL, blob)
    if legal and legal not in company_name:
        out["legal_person"] = legal
    date = _first(_DATE, blob)
    if date:
        out["establish_date"] = date.replace("年", "-").replace("月", "-").replace("日", "").strip("-")
    cap = _first(_CAPITAL, blob)
    if cap:
        out["registered_capital_wan"] = cap.replace(",", "")
    addr = _first(_ADDRESS, blob)
    if addr and company_name not in addr:
        out["address"] = addr
        # street = last segment before 号 often
        if "街道" in addr:
            sm = re.search(r"([\u4e00-\u9fff]{2,12}街道)", addr)
            if sm:
                out["street"] = sm.group(1)
        elif "镇" in addr:
            sm = re.search(r"([\u4e00-\u9fff]{2,12}镇)", addr)
            if sm:
                out["street"] = sm.group(1)
    district = _pick_district(blob)
    if district:
        out["district"] = district
    patents = _first(_PATENT, blob)
    if patents:
        out["patents"] = f"公开提及约{patents}项"
    honors = sorted(set(_HONOR.findall(blob)))
    if honors:
        out["honors"] = "、".join(honors)
        out["qualifications"] = "、".join(honors)
    # core tech: short sentences containing product keywords
    for line in blob.splitlines():
        line = line.strip()
        if 12 <= len(line) <= 120 and any(
            k in line for k in ("产品", "技术", "服务", "解决方案", "平台", "系统", "研发")
        ):
            if company_name and company_name[:4] in line and len(line) < 20:
                continue
            out["core_tech"] = line
            break
    return out


def enrich_company_profile(
    name: str,
    props: dict[str, Any] | None = None,
    *,
    region: str = "",
    industry: str = "科技",
    fetch_pages: int = 2,
    search_num: int = 6,
    sleep_s: float = 0.4,
) -> dict[str, Any]:
    """
    Fill standard profile fields via public search + page extract.
    Does not use paid enterprise databases; many rows will stay partial.
    """
    name = clean_company_name(name)
    props = enrich_company_props(
        name, normalize_props(props), default_region=region, default_industry=industry or "科技"
    )
    missing = missing_profile_fields(props)
    if not missing:
        props["filter_tag"] = props.get("filter_tag") or "profile_complete"
        return props

    queries = [
        f"{name} 统一社会信用代码 法人 注册资本",
        f"{name} {region} 简介 产品",
        f"{name} 高新技术企业 专利",
    ]
    snippets: list[str] = []
    urls: list[str] = []
    for q in queries[:2]:
        hits = do_search(q, num=search_num)
        time.sleep(sleep_s)
        for h in hits:
            if not isinstance(h, dict) or h.get("error"):
                continue
            snip = str(h.get("snippet") or "")
            title = str(h.get("title") or "")
            url = str(h.get("url") or h.get("href") or "")
            snippets.append(f"{title}\n{snip}")
            if url and url not in urls:
                urls.append(url)
    # Prefer official / company / encyclopedia pages for fetch
    prefer = [
        u
        for u in urls
        if any(x in u for x in ("gov.cn", "baike", "wikipedia", "tianyancha", "qcc", "aiqicha", "官网"))
    ] or urls
    for url in prefer[:fetch_pages]:
        page = do_fetch(url, max_chars=8000, strategy="auto")
        time.sleep(sleep_s)
        if isinstance(page, dict) and page.get("content"):
            snippets.append(str(page.get("title") or "") + "\n" + str(page["content"]))
            props.setdefault("source_url", url)

    blob = "\n".join(snippets)
    extracted = extract_fields_from_text(blob, company_name=name)
    for k, v in extracted.items():
        if v and not str(props.get(k) or "").strip():
            props[k] = v

    # taxonomy after we may have core_tech text
    if props.get("core_tech"):
        props["sub_industry"] = infer_sub_industry(
            name, {**props, "note": props.get("core_tech")}
        )
    props["role"] = infer_role(name, props)
    if props.get("role") and props["role"] != "未标注角色":
        quals = str(props.get("qualifications") or "")
        if props["role"] not in quals:
            props["qualifications"] = "、".join(x for x in [quals, props["role"]] if x)

    if not props.get("industry_chain"):
        # coarse chain from role/sub
        sub = str(props.get("sub_industry") or "")
        if any(k in sub for k in ("软件", "平台", "云", "互联网", "信息")):
            props["industry_chain"] = "中游"
        elif any(k in sub for k in ("材料", "芯片", "半导体", "元器件")):
            props["industry_chain"] = "上游"
        else:
            props["industry_chain"] = "中游"

    if not props.get("classify_reason"):
        props["classify_reason"] = (
            f"公开检索补全；细分={props.get('sub_industry') or '未细分'}；"
            f"角色={props.get('role') or '未标注'}"
        )
    src = str(props.get("source") or "")
    if "public_web_enrich" not in src:
        props["source"] = (src + "+public_web_enrich").strip("+")
    still = missing_profile_fields(props)
    props["filter_tag"] = "profile_partial" if still else "profile_complete"
    props["profile_missing"] = ",".join(still)
    return props


def enrich_scope_profiles(
    store,
    scope: str,
    *,
    limit: int = 50,
    only_missing: bool = True,
    fetch_pages: int = 1,
    region: str = "",
    industry: str = "科技",
) -> dict[str, Any]:
    """Enrich up to `limit` companies in a scope; rewrite props and return stats."""
    if not region and "_" in scope:
        region, industry = scope.split("_", 1)
    nodes = store.query_nodes(label="Company", scope=scope, limit=100000)
    updated = 0
    scanned = 0
    filled_fields: dict[str, int] = {}
    for node in nodes:
        if updated >= limit:
            break
        props = normalize_props(node.get("properties") or {})
        name = clean_company_name(str(props.get("name") or node["id"]))
        if only_missing and not missing_profile_fields(props):
            continue
        scanned += 1
        before = {k: props.get(k) for k in missing_profile_fields(props)}
        enriched = enrich_company_profile(
            name,
            props,
            region=region,
            industry=industry or "科技",
            fetch_pages=fetch_pages,
        )
        store.upsert_node(
            node["id"],
            labels=node.get("labels") or ["Company"],
            properties=enriched,
            scope=scope,
        )
        updated += 1
        for k, v in enriched.items():
            if v and not before.get(k):
                filled_fields[k] = filled_fields.get(k, 0) + 1
    return {
        "scope": scope,
        "scanned": scanned,
        "updated": updated,
        "limit": limit,
        "filled_field_counts": sorted(filled_fields.items(), key=lambda x: -x[1])[:20],
    }

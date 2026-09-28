"""Company name extraction and multi-query discovery (maximize coverage)."""

from __future__ import annotations

import re
from typing import Any

from industry_graph_mcp.search_fetch import do_fetch, do_search

# Chinese legal entity suffixes (longest first)
_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "有限公司",
    "集团有限公司",
    "科技有限公司",
    "技术有限公司",
    "实业有限公司",
    "发展有限公司",
    "投资有限公司",
    "控股有限公司",
)

_COMPANY_RE = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9（）()·\-]{2,40}(?:"
    + "|".join(_SUFFIXES)
    + r"))"
)

_PREFIX_STRIP = re.compile(
    r"^(?:另有|以及|包括|含有|还有|其中|分别为|分别是|和|与|及|、|，|,|;|；|:|：|"
    r"的|等|为|是|由)+"
)

# Extra sector lenses when industry is broad (科技/产业)
_TECH_SECTORS = [
    "数字经济", "人工智能", "半导体", "芯片", "软件", "互联网", "云计算",
    "大数据", "安防", "机器人", "电商", "金融科技", "生物医药", "新能源",
    "智能制造", "工业软件", "游戏", "区块链", "物联网", "专精特新",
]

_DISTRICTS = {
    "杭州": ["滨江", "余杭", "西湖", "萧山", "拱墅", "上城", "临平", "钱塘"],
    "北京": ["海淀", "朝阳", "昌平", "大兴", "丰台"],
    "上海": ["浦东", "徐汇", "闵行", "嘉定", "松江"],
    "深圳": ["南山", "福田", "宝安", "龙岗", "龙华"],
    "广州": ["天河", "黄埔", "番禺", "海珠"],
}


def extract_company_names(*texts: str, limit: int = 2000) -> list[str]:
    """Extract likely company legal names from free text."""
    seen: set[str] = set()
    out: list[str] = []
    blob = "\n".join(t for t in texts if t)
    for m in _COMPANY_RE.finditer(blob):
        name = m.group(1).strip()
        name = name.lstrip("《》【】「」\"'‘’“”、，,.;；:： ")
        name = _PREFIX_STRIP.sub("", name).strip()
        if not name or not re.match(r"^[\u4e00-\u9fffA-Za-z(（]", name):
            continue
        if len(name) < 4 or len(name) > 40:
            continue
        if name.endswith("名单") or name.endswith("目录") or name.endswith("公告"):
            continue
        if name in seen:
            continue
        if sum(1 for c in name if "\u4e00" <= c <= "\u9fff") < 2:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= limit:
            break
    return out


def build_discovery_queries(region: str, industry: str, maximize: bool = True) -> list[str]:
    base = f"{region} {industry}".strip()
    queries = [
        f"{base} 龙头企业 名单",
        f"{base} 百强企业 名单",
        f"{base} 专精特新 名单",
        f"{base} 高新技术企业 名单",
        f"{base} 独角兽 企业 名单",
        f"{base} 拟上市 企业 名单",
        f"{base} 上市公司 名单",
        f"{base} 重点企业 名录 site:gov.cn",
        f"{base} 企业名录 site:gov.cn",
        f"{base} 中标 企业",
        f"{base} 单项冠军 企业",
        f"{base} 隐形冠军",
        f"{region} 民营企业 百强",
        f"{region} 高新区 企业 名单",
    ]
    if maximize and (industry in ("科技", "产业", "互联网", "数字经济") or "科技" in industry):
        for sec in _TECH_SECTORS:
            queries.append(f"{region} {sec} 企业 名单")
            queries.append(f"{region} {sec} 龙头公司")
        for dist in _DISTRICTS.get(region, [])[:6]:
            queries.append(f"{region}{dist} {industry} 企业 名单")
            queries.append(f"{dist} 高新技术企业 名单 {region}")
    # dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def discover_companies(
    region: str,
    industry: str,
    max_companies: int = 500,
    results_per_query: int = 15,
    fetch_top_pages: int = 12,
    maximize: bool = True,
) -> dict[str, Any]:
    """
    Multi-query search + page fetch to collect as many company candidates as possible.
    """
    max_companies = max(50, min(int(max_companies or 500), 2000))
    queries = build_discovery_queries(region, industry, maximize=maximize)
    search_hits: list[dict[str, Any]] = []
    evidence: dict[str, list[dict[str, str]]] = {}

    for q in queries:
        hits = do_search(q, num=results_per_query)
        for h in hits:
            if not isinstance(h, dict) or "error" in h:
                continue
            h = {**h, "query": q}
            search_hits.append(h)
            for name in extract_company_names(h.get("title", ""), h.get("snippet", "")):
                evidence.setdefault(name, []).append(
                    {
                        "query": q,
                        "url": h.get("url", ""),
                        "title": h.get("title", ""),
                        "snippet": (h.get("snippet") or "")[:200],
                    }
                )

    fetched: list[dict[str, Any]] = []
    urls_seen: set[str] = set()
    # Prefer list-like pages
    ranked_hits = sorted(
        search_hits,
        key=lambda h: (
            0
            if any(
                k in (h.get("title") or "") + (h.get("url") or "")
                for k in ("名单", "名录", "百强", "专精特新", "独角兽", "拟上市", "gov", "高新区")
            )
            else 1,
            -(len(h.get("snippet") or "")),
        ),
    )
    for h in ranked_hits:
        url = h.get("url") or ""
        if not url or url in urls_seen:
            continue
        urls_seen.add(url)
        page = do_fetch(url, max_chars=30000)
        fetched.append({"url": url, "ok": "error" not in page, "title": page.get("title", "")})
        if "error" in page:
            if len(fetched) >= fetch_top_pages:
                break
            continue
        for name in extract_company_names(page.get("title", ""), page.get("content", "")):
            evidence.setdefault(name, []).append(
                {
                    "query": "fetch",
                    "url": url,
                    "title": page.get("title", ""),
                    "snippet": "from_fetched_page",
                }
            )
        if len(fetched) >= fetch_top_pages:
            break

    ranked = sorted(evidence.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    companies = []
    for name, ev in ranked[:max_companies]:
        companies.append(
            {
                "name": name,
                "evidence_count": len(ev),
                "evidence": ev[:3],
                "region": region,
                "industry": industry,
            }
        )

    return {
        "region": region,
        "industry": industry,
        "maximize": maximize,
        "query_count": len(queries),
        "queries": queries[:30],  # truncate for tool payload size
        "queries_total": len(queries),
        "search_hits": len(search_hits),
        "pages_fetched": len(fetched),
        "fetched": fetched,
        "company_count": len(companies),
        "companies": companies,
        "note": (
            "尽可能多地从公开网页发现候选；非工商库全量。"
            "若仍偏少，可再调大 max_companies / fetch_top_pages，或换细分赛道再跑一轮。"
        ),
    }

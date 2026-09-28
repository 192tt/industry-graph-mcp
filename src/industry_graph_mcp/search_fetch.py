"""Local search & fetch (ported from fan31415/company_search_skills pattern)."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any
from urllib.parse import urlparse

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _extract_text(html: str, url: str) -> str:
    try:
        import trafilatura

        text = trafilatura.extract(
            html, url=url, include_comments=False, include_tables=True
        )
        if text and len(text) > 200:
            return text
    except Exception:
        pass
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
        tag.decompose()
    body = soup.find("main") or soup.find("article") or soup.find(id="content") or soup.body
    raw = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return "\n".join(lines)


def _build_result(url: str, status: int, title: str, text: str, strategy: str, max_chars: int) -> dict[str, Any]:
    return {
        "url": url,
        "status": status,
        "title": title,
        "strategy": strategy,
        "content": text[:max_chars],
        "truncated": len(text) > max_chars,
        "total_chars": len(text),
    }


def _fetch_direct(url: str, timeout: int, max_chars: int) -> dict[str, Any]:
    import requests
    from bs4 import BeautifulSoup

    session = requests.Session()
    session.headers.update(_BROWSER_HEADERS)
    try:
        root = f"{urlparse(url).scheme}://{urlparse(url).netloc}/"
        if root != url:
            session.get(root, timeout=timeout, allow_redirects=True)
            time.sleep(0.3)
    except Exception:
        pass
    resp = session.get(url, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    soup = BeautifulSoup(resp.text, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    text = _extract_text(resp.text, url)
    return _build_result(url, resp.status_code, title, text, "direct", max_chars)


def _fetch_jina(url: str, timeout: int, max_chars: int) -> dict[str, Any]:
    import requests

    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        "User-Agent": _BROWSER_HEADERS["User-Agent"],
        "Accept": "text/plain, text/markdown, */*",
        "X-Return-Format": "markdown",
    }
    resp = requests.get(jina_url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    text = resp.text.strip()
    title = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            title = line.lstrip("# ").strip()
            break
    return _build_result(url, resp.status_code, title, text, "jina", max_chars)


def _fetch_archive(url: str, timeout: int, max_chars: int) -> dict[str, Any]:
    import requests
    from bs4 import BeautifulSoup

    avail = requests.get(
        "https://archive.org/wayback/available",
        params={"url": url},
        timeout=timeout,
    ).json()
    closest = avail.get("archived_snapshots", {}).get("closest", {})
    if not closest.get("available"):
        raise ValueError("No Wayback Machine snapshot found")
    archive_url = closest["url"]
    resp = requests.get(archive_url, headers=_BROWSER_HEADERS, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    soup = BeautifulSoup(resp.text, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    text = _extract_text(resp.text, archive_url)
    result = _build_result(url, resp.status_code, title, text, "archive", max_chars)
    result["archive_url"] = archive_url
    result["archive_timestamp"] = closest.get("timestamp", "")
    return result


_STRATEGIES = {
    "direct": _fetch_direct,
    "jina": _fetch_jina,
    "archive": _fetch_archive,
}


def do_fetch(
    url: str,
    timeout: int = 15,
    max_chars: int = 12000,
    strategy: str = "auto",
) -> dict[str, Any]:
    try:
        import requests  # noqa: F401
        from bs4 import BeautifulSoup  # noqa: F401
    except ImportError:
        return {"error": "missing deps: pip install requests beautifulsoup4 lxml"}

    order = list(_STRATEGIES.keys()) if strategy == "auto" else [strategy]
    errors: dict[str, str] = {}
    for name in order:
        try:
            return _STRATEGIES[name](url, timeout, max_chars)
        except Exception as e:
            errors[name] = str(e)
            if strategy != "auto":
                break
    return {"url": url, "error": "all strategies failed", "details": errors}


def do_search(query: str, num: int = 10) -> list[dict[str, Any]]:
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # type: ignore
        except ImportError:
            return [{"error": "missing dep: pip install ddgs"}]
    try:
        with DDGS() as ddgs:
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                }
                for r in ddgs.text(query, max_results=num)
            ]
    except Exception as e:
        return [{"error": str(e)}]


def survey_plan(utterance: str, target_companies: int = 500) -> dict[str, Any]:
    """Build a search plan from a natural-language survey request.

    Default goal is maximize public coverage (target_companies=500 ceiling hint).
    """
    text = (utterance or "").strip()
    region = ""
    industry = ""
    # Longer / more specific names first to avoid partial mis-hits
    regions = [
        "内蒙古", "黑龙江", "新疆", "宁夏", "广西", "西藏", "香港", "澳门", "台湾",
        "海淀区", "朝阳区", "浦东", "滨江", "余杭", "萧山",
        "杭州", "宁波", "温州", "苏州", "南京", "无锡", "常州", "合肥", "福州",
        "厦门", "青岛", "济南", "郑州", "长沙", "武汉", "成都", "西安", "昆明",
        "贵阳", "南昌", "石家庄", "太原", "沈阳", "大连", "长春", "哈尔滨",
        "南宁", "海口", "三亚", "兰州", "银川", "西宁", "乌鲁木齐",
        "东莞", "佛山", "珠海", "中山", "惠州", "嘉兴", "绍兴", "金华", "台州",
        "广东", "广州", "深圳", "北京", "上海", "浙江", "江苏", "四川", "重庆",
        "山东", "湖北", "湖南", "福建", "安徽", "天津", "河北", "河南", "海淀",
        "辽宁", "吉林", "云南", "贵州", "江西", "山西", "陕西", "甘肃", "青海",
        "海南",
    ]
    for r in regions:
        if r in text:
            region = r
            break
    industries = [
        "科技养老", "智慧养老", "智能制造", "生物医药", "人工智能", "数字经济",
        "高新技术", "科技企业", "硬科技", "金融科技", "跨境电商",
        "制造业", "养老", "新能源", "半导体", "机器人", "软件", "互联网",
        "新材料", "医药", "芯片", "安防", "云计算", "大数据", "电商", "科技",
    ]
    for ind in industries:
        if ind in text:
            industry = ind
            break
    if industry == "科技企业":
        industry = "科技"
    if not industry:
        if "企业" in text and ("科技" in text or "高新" in text):
            industry = "科技"
        else:
            industry = "产业"
    if not region:
        region = "全国"
    # User requirement: 尽可能多 — default high ceiling
    target = max(100, min(int(target_companies or 500), 2000))
    scope = f"{region}_{industry}".replace(" ", "")
    from industry_graph_mcp.discover import build_discovery_queries

    queries = build_discovery_queries(region, industry, maximize=True)
    return {
        "utterance": text,
        "region": region,
        "industry": industry,
        "scope": scope,
        "target_companies": target,
        "goal": "尽可能多（公开源能抓到的都入库，直到边际收益很低）",
        "queries": queries[:40],
        "queries_total": len(queries),
        "steps": [
            f"discover_companies(region, industry, max_companies={target}, maximize=True) 尽量拉满候选",
            "graph_upsert_companies_batch 全量写入名称（先求数量，再挑 Top 补字段）",
            "若 company_count 仍增长空间大：按细分赛道/区县再跑一轮 discover 或 web_search，继续 upsert",
            "不要因为已经有几十家就停止；目标是公开检索下尽可能多",
            "graph_add_relation / graph_stats / graph_open_viewer / save_report",
        ],
        "coverage_note": (
            "公开网页检索无法达到工商全量；策略是多 query + 多名单页 + 多赛道，"
            f"尽量接近 {target} 家或直到搜不到新名。"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Local search & fetch")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("search")
    sp.add_argument("query")
    sp.add_argument("--num", type=int, default=10)
    fp = sub.add_parser("fetch")
    fp.add_argument("url")
    fp.add_argument("--timeout", type=int, default=15)
    fp.add_argument("--max-chars", type=int, default=12000)
    fp.add_argument("--strategy", choices=["auto", "direct", "jina", "archive"], default="auto")
    pp = sub.add_parser("plan")
    pp.add_argument("utterance")
    args = parser.parse_args()
    if args.cmd == "search":
        result: Any = do_search(args.query, args.num)
    elif args.cmd == "fetch":
        result = do_fetch(args.url, args.timeout, args.max_chars, args.strategy)
    else:
        result = survey_plan(args.utterance)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

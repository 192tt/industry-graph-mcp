"""First-time setup wizard — Neo4j optional, SQLite default. All paths on D:."""

from __future__ import annotations

import argparse
import json
import sys

from industry_graph_mcp.config import (
    AppConfig,
    config_path,
    data_dir,
    data_root,
    load_config,
    reports_dir,
    save_config,
)


def detect_neo4j(uri: str, user: str, password: str) -> tuple[bool, str]:
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run("RETURN 1").consume()
        driver.close()
        return True, "ok"
    except Exception as e:
        return False, str(e)


def run_wizard(
    backend: str | None = None,
    neo4j_uri: str = "bolt://127.0.0.1:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "password",
    non_interactive: bool = False,
) -> AppConfig:
    data_root()
    data_dir()
    reports_dir()
    cfg = load_config()
    cfg.neo4j_uri = neo4j_uri
    cfg.neo4j_user = neo4j_user
    cfg.neo4j_password = neo4j_password
    cfg.sqlite_path = str(data_dir() / "graph.db")

    ok, msg = detect_neo4j(neo4j_uri, neo4j_user, neo4j_password)

    if backend in ("sqlite", "neo4j"):
        chosen = backend
    elif non_interactive:
        chosen = "neo4j" if ok else "sqlite"
    else:
        print("=== Industry Graph MCP 首次配置 ===")
        print(f"数据根目录: {data_root()}")
        print(f"Neo4j 检测 ({neo4j_uri}): {'可用' if ok else '不可用'} ({msg})")
        print()
        print("请选择图谱后端:")
        print("  1) SQLite 平替（推荐，无需安装 Neo4j）")
        print("  2) Neo4j（需本机已安装并可连接）")
        print("  3) 自动（有 Neo4j 用 Neo4j，否则 SQLite）")
        choice = input("输入 1/2/3 [默认3]: ").strip() or "3"
        if choice == "1":
            chosen = "sqlite"
        elif choice == "2":
            chosen = "neo4j"
        else:
            chosen = "neo4j" if ok else "sqlite"

    if chosen == "neo4j" and not ok:
        print(f"警告: Neo4j 不可用 ({msg})，已回退到 SQLite 平替。", file=sys.stderr)
        print("如需 Neo4j，可安装 Neo4j Desktop / Docker 后重新运行: industry-graph-setup")
        chosen = "sqlite"

    cfg.graph_backend = chosen  # type: ignore[assignment]
    path = save_config(cfg)
    print(json.dumps({"saved": str(path), "config": cfg.to_dict()}, ensure_ascii=False, indent=2))
    return cfg


def main() -> None:
    parser = argparse.ArgumentParser(description="Industry Graph MCP setup wizard")
    parser.add_argument("--backend", choices=["sqlite", "neo4j"], default=None)
    parser.add_argument("--neo4j-uri", default="bolt://127.0.0.1:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="password")
    parser.add_argument("-y", "--yes", action="store_true", help="non-interactive")
    args = parser.parse_args()
    run_wizard(
        backend=args.backend,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        non_interactive=args.yes,
    )
    print(f"配置文件: {config_path()}")


if __name__ == "__main__":
    main()

"""Configuration under D:\\industry-graph-mcp by default."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from industry_graph_mcp import DEFAULT_DATA_ROOT

GraphBackend = Literal["sqlite", "neo4j"]


def data_root() -> Path:
    root = Path(os.environ.get("INDUSTRY_GRAPH_MCP_HOME", DEFAULT_DATA_ROOT))
    root.mkdir(parents=True, exist_ok=True)
    return root


def config_path() -> Path:
    return data_root() / "config.json"


def data_dir() -> Path:
    p = data_root() / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def reports_dir() -> Path:
    p = data_root() / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir() -> Path:
    p = data_root() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class AppConfig:
    graph_backend: GraphBackend = "sqlite"
    sqlite_path: str = ""
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    default_scope: str = "default"
    dist_base_url: str = "https://YOUR_SERVER/industry-graph-mcp"
    created: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def resolved_sqlite_path(self) -> Path:
        if self.sqlite_path:
            return Path(self.sqlite_path)
        return data_dir() / "graph.db"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AppConfig":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in d.items() if k in known and k != "extra"}
        extra = {k: v for k, v in d.items() if k not in known}
        if "extra" in d and isinstance(d["extra"], dict):
            extra.update(d["extra"])
        cfg = cls(**kwargs)
        cfg.extra = extra
        return cfg


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        cfg = AppConfig()
        cfg.sqlite_path = str(data_dir() / "graph.db")
        return cfg
    with path.open("r", encoding="utf-8") as f:
        return AppConfig.from_dict(json.load(f))


def save_config(cfg: AppConfig) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cfg.sqlite_path:
        cfg.sqlite_path = str(data_dir() / "graph.db")
    cfg.created = True
    with path.open("w", encoding="utf-8") as f:
        json.dump(cfg.to_dict(), f, ensure_ascii=False, indent=2)
    return path

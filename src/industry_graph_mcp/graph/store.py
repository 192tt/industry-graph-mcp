"""Unified GraphStore abstract interface + factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class GraphStore(ABC):
    backend_name: str = "abstract"

    @abstractmethod
    def upsert_node(
        self,
        node_id: str,
        labels: list[str] | None = None,
        properties: dict[str, Any] | None = None,
        scope: str = "default",
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    def add_relation(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
        scope: str = "default",
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    def get_node(self, node_id: str, scope: str | None = None) -> dict[str, Any] | None:
        ...

    @abstractmethod
    def delete_node(self, node_id: str, scope: str | None = None) -> bool:
        ...

    @abstractmethod
    def delete_relation(
        self,
        source_id: str,
        target_id: str,
        rel_type: str | None = None,
        scope: str | None = None,
    ) -> int:
        ...

    @abstractmethod
    def query_nodes(
        self,
        label: str | None = None,
        scope: str | None = None,
        where: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def query_relations(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        rel_type: str | None = None,
        scope: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def stats(self, scope: str | None = None) -> dict[str, Any]:
        ...

    @abstractmethod
    def export_graph(self, scope: str | None = None) -> dict[str, Any]:
        ...

    @abstractmethod
    def import_nodes_edges(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        scope: str = "default",
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    def close(self) -> None:
        ...


def get_store():
    """Factory based on local config under D:\\industry-graph-mcp."""
    from industry_graph_mcp.config import load_config
    from industry_graph_mcp.graph.neo4j_store import Neo4jStore
    from industry_graph_mcp.graph.sqlite_store import SqliteStore

    cfg = load_config()
    if cfg.graph_backend == "neo4j":
        try:
            store = Neo4jStore(
                uri=cfg.neo4j_uri,
                user=cfg.neo4j_user,
                password=cfg.neo4j_password,
            )
            store.ping()
            return store
        except Exception as e:
            store = SqliteStore(cfg.resolved_sqlite_path())
            store._fallback_reason = f"neo4j_unavailable: {e}"
            return store
    return SqliteStore(cfg.resolved_sqlite_path())

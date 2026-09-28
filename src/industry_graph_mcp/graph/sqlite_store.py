"""SQLite graph store — no Neo4j required."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from industry_graph_mcp.graph.store import GraphStore


class SqliteStore(GraphStore):
    backend_name = "sqlite"

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fallback_reason: str | None = None
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'default',
                labels TEXT NOT NULL DEFAULT '[]',
                properties TEXT NOT NULL DEFAULT '{}',
                updated_at REAL NOT NULL,
                PRIMARY KEY (id, scope)
            );
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL DEFAULT 'default',
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                rel_type TEXT NOT NULL,
                properties TEXT NOT NULL DEFAULT '{}',
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(source_id, scope);
            CREATE INDEX IF NOT EXISTS idx_edges_tgt ON edges(target_id, scope);
            CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(rel_type, scope);
            """
        )
        self._conn.commit()

    def upsert_node(
        self,
        node_id: str,
        labels: list[str] | None = None,
        properties: dict[str, Any] | None = None,
        scope: str = "default",
    ) -> dict[str, Any]:
        labels = labels or ["Company"]
        properties = properties or {}
        existing = self.get_node(node_id, scope)
        if existing:
            merged_props = {**existing.get("properties", {}), **properties}
            merged_labels = sorted(set(existing.get("labels", []) + labels))
        else:
            merged_props = properties
            merged_labels = labels
        now = time.time()
        self._conn.execute(
            """
            INSERT INTO nodes(id, scope, labels, properties, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id, scope) DO UPDATE SET
              labels=excluded.labels,
              properties=excluded.properties,
              updated_at=excluded.updated_at
            """,
            (node_id, scope, json.dumps(merged_labels, ensure_ascii=False),
             json.dumps(merged_props, ensure_ascii=False), now),
        )
        self._conn.commit()
        return {"id": node_id, "scope": scope, "labels": merged_labels, "properties": merged_props}

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
        scope: str = "default",
    ) -> dict[str, Any]:
        properties = properties or {}
        # Ensure endpoints exist
        if not self.get_node(source_id, scope):
            self.upsert_node(source_id, ["Entity"], {"name": source_id}, scope)
        if not self.get_node(target_id, scope):
            self.upsert_node(target_id, ["Entity"], {"name": target_id}, scope)
        now = time.time()
        cur = self._conn.execute(
            """
            INSERT INTO edges(scope, source_id, target_id, rel_type, properties, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (scope, source_id, target_id, rel_type,
             json.dumps(properties, ensure_ascii=False), now),
        )
        self._conn.commit()
        return {
            "id": cur.lastrowid,
            "scope": scope,
            "source_id": source_id,
            "target_id": target_id,
            "rel_type": rel_type,
            "properties": properties,
        }

    def get_node(self, node_id: str, scope: str | None = None) -> dict[str, Any] | None:
        if scope:
            row = self._conn.execute(
                "SELECT * FROM nodes WHERE id=? AND scope=?", (node_id, scope)
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM nodes WHERE id=? ORDER BY updated_at DESC LIMIT 1",
                (node_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_node(row)

    def delete_node(self, node_id: str, scope: str | None = None) -> bool:
        if scope:
            cur = self._conn.execute(
                "DELETE FROM nodes WHERE id=? AND scope=?", (node_id, scope)
            )
            self._conn.execute(
                "DELETE FROM edges WHERE scope=? AND (source_id=? OR target_id=?)",
                (scope, node_id, node_id),
            )
        else:
            cur = self._conn.execute("DELETE FROM nodes WHERE id=?", (node_id,))
            self._conn.execute(
                "DELETE FROM edges WHERE source_id=? OR target_id=?",
                (node_id, node_id),
            )
        self._conn.commit()
        return cur.rowcount > 0

    def delete_relation(
        self,
        source_id: str,
        target_id: str,
        rel_type: str | None = None,
        scope: str | None = None,
    ) -> int:
        sql = "DELETE FROM edges WHERE source_id=? AND target_id=?"
        params: list[Any] = [source_id, target_id]
        if rel_type:
            sql += " AND rel_type=?"
            params.append(rel_type)
        if scope:
            sql += " AND scope=?"
            params.append(scope)
        cur = self._conn.execute(sql, params)
        self._conn.commit()
        return cur.rowcount

    def query_nodes(
        self,
        label: str | None = None,
        scope: str | None = None,
        where: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM nodes WHERE 1=1"
        params: list[Any] = []
        if scope:
            sql += " AND scope=?"
            params.append(scope)
        rows = self._conn.execute(sql + " ORDER BY updated_at DESC", params).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            node = self._row_to_node(row)
            if label and label not in node["labels"]:
                continue
            if where:
                props = node["properties"]
                if any(props.get(k) != v for k, v in where.items()):
                    continue
            out.append(node)
            if len(out) >= limit:
                break
        return out

    def query_relations(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        rel_type: str | None = None,
        scope: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM edges WHERE 1=1"
        params: list[Any] = []
        if source_id:
            sql += " AND source_id=?"
            params.append(source_id)
        if target_id:
            sql += " AND target_id=?"
            params.append(target_id)
        if rel_type:
            sql += " AND rel_type=?"
            params.append(rel_type)
        if scope:
            sql += " AND scope=?"
            params.append(scope)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def stats(self, scope: str | None = None) -> dict[str, Any]:
        if scope:
            n = self._conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE scope=?", (scope,)
            ).fetchone()[0]
            e = self._conn.execute(
                "SELECT COUNT(*) FROM edges WHERE scope=?", (scope,)
            ).fetchone()[0]
        else:
            n = self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            e = self._conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        result = {
            "backend": self.backend_name,
            "db_path": str(self.db_path),
            "nodes": n,
            "edges": e,
            "scope": scope or "*",
        }
        if self._fallback_reason:
            result["fallback_reason"] = self._fallback_reason
        return result

    def export_graph(self, scope: str | None = None) -> dict[str, Any]:
        return {
            "backend": self.backend_name,
            "scope": scope or "*",
            "nodes": self.query_nodes(scope=scope, limit=100000),
            "edges": self.query_relations(scope=scope, limit=100000),
        }

    def import_nodes_edges(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        scope: str = "default",
    ) -> dict[str, Any]:
        n_count = 0
        for node in nodes:
            nid = str(node.get("id") or node.get("properties", {}).get("name") or "")
            if not nid:
                continue
            self.upsert_node(
                nid,
                labels=node.get("labels") or ["Company"],
                properties=node.get("properties") or {k: v for k, v in node.items() if k not in ("id", "labels", "scope")},
                scope=node.get("scope") or scope,
            )
            n_count += 1
        e_count = 0
        for edge in edges:
            src = edge.get("source_id") or edge.get("source")
            tgt = edge.get("target_id") or edge.get("target")
            rel = edge.get("rel_type") or edge.get("type") or "RELATED"
            if not src or not tgt:
                continue
            self.add_relation(
                str(src),
                str(tgt),
                str(rel),
                properties=edge.get("properties") or {},
                scope=edge.get("scope") or scope,
            )
            e_count += 1
        return {"imported_nodes": n_count, "imported_edges": e_count, "scope": scope}

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row_to_node(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "scope": row["scope"],
            "labels": json.loads(row["labels"]),
            "properties": json.loads(row["properties"]),
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _row_to_edge(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "scope": row["scope"],
            "source_id": row["source_id"],
            "target_id": row["target_id"],
            "rel_type": row["rel_type"],
            "properties": json.loads(row["properties"]),
            "updated_at": row["updated_at"],
        }

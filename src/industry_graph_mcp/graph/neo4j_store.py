"""Neo4j graph store adapter (optional)."""

from __future__ import annotations

import time
from typing import Any

from industry_graph_mcp.graph.store import GraphStore


class Neo4jStore(GraphStore):
    backend_name = "neo4j"

    def __init__(self, uri: str, user: str, password: str):
        from neo4j import GraphDatabase

        self.uri = uri
        self.user = user
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def ping(self) -> None:
        with self._driver.session() as session:
            session.run("RETURN 1").consume()

    def upsert_node(
        self,
        node_id: str,
        labels: list[str] | None = None,
        properties: dict[str, Any] | None = None,
        scope: str = "default",
    ) -> dict[str, Any]:
        labels = labels or ["Company"]
        properties = dict(properties or {})
        properties["id"] = node_id
        properties["graph_scope"] = scope
        properties["updated_at"] = time.time()
        label_str = ":".join(self._safe_labels(labels))
        cypher = f"""
        MERGE (n:{label_str} {{id: $id, graph_scope: $scope}})
        SET n += $props
        RETURN n
        """
        with self._driver.session() as session:
            session.run(cypher, id=node_id, scope=scope, props=properties).consume()
        return {"id": node_id, "scope": scope, "labels": labels, "properties": properties}

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
        scope: str = "default",
    ) -> dict[str, Any]:
        properties = dict(properties or {})
        properties["graph_scope"] = scope
        properties["updated_at"] = time.time()
        rel = self._safe_rel(rel_type)
        cypher = f"""
        MERGE (a:Entity {{id: $src, graph_scope: $scope}})
        MERGE (b:Entity {{id: $tgt, graph_scope: $scope}})
        MERGE (a)-[r:{rel}]->(b)
        SET r += $props
        RETURN type(r) AS rel_type
        """
        with self._driver.session() as session:
            session.run(
                cypher, src=source_id, tgt=target_id, scope=scope, props=properties
            ).consume()
        return {
            "source_id": source_id,
            "target_id": target_id,
            "rel_type": rel_type,
            "properties": properties,
            "scope": scope,
        }

    def get_node(self, node_id: str, scope: str | None = None) -> dict[str, Any] | None:
        if scope:
            cypher = "MATCH (n {id:$id, graph_scope:$scope}) RETURN n, labels(n) AS labels LIMIT 1"
            params: dict[str, Any] = {"id": node_id, "scope": scope}
        else:
            cypher = "MATCH (n {id:$id}) RETURN n, labels(n) AS labels LIMIT 1"
            params = {"id": node_id}
        with self._driver.session() as session:
            rec = session.run(cypher, **params).single()
            if not rec:
                return None
            props = dict(rec["n"])
            return {
                "id": node_id,
                "scope": props.get("graph_scope", scope or "default"),
                "labels": list(rec["labels"]),
                "properties": props,
            }

    def delete_node(self, node_id: str, scope: str | None = None) -> bool:
        if scope:
            cypher = "MATCH (n {id:$id, graph_scope:$scope}) DETACH DELETE n RETURN count(*) AS c"
            params: dict[str, Any] = {"id": node_id, "scope": scope}
        else:
            cypher = "MATCH (n {id:$id}) DETACH DELETE n RETURN count(*) AS c"
            params = {"id": node_id}
        with self._driver.session() as session:
            rec = session.run(cypher, **params).single()
            return bool(rec and rec["c"] > 0)

    def delete_relation(
        self,
        source_id: str,
        target_id: str,
        rel_type: str | None = None,
        scope: str | None = None,
    ) -> int:
        if rel_type:
            rel = self._safe_rel(rel_type)
            cypher = f"""
            MATCH (a {{id:$src}})-[r:{rel}]->(b {{id:$tgt}})
            WHERE $scope IS NULL OR a.graph_scope = $scope
            DELETE r RETURN count(*) AS c
            """
        else:
            cypher = """
            MATCH (a {id:$src})-[r]->(b {id:$tgt})
            WHERE $scope IS NULL OR a.graph_scope = $scope
            DELETE r RETURN count(*) AS c
            """
        with self._driver.session() as session:
            rec = session.run(
                cypher, src=source_id, tgt=target_id, scope=scope
            ).single()
            return int(rec["c"]) if rec else 0

    def query_nodes(
        self,
        label: str | None = None,
        scope: str | None = None,
        where: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        label_part = f":{self._safe_labels([label])[0]}" if label else ""
        cypher = f"MATCH (n{label_part}) WHERE 1=1"
        params: dict[str, Any] = {"limit": limit}
        if scope:
            cypher += " AND n.graph_scope = $scope"
            params["scope"] = scope
        cypher += " RETURN n, labels(n) AS labels LIMIT $limit"
        out: list[dict[str, Any]] = []
        with self._driver.session() as session:
            for rec in session.run(cypher, **params):
                props = dict(rec["n"])
                if where and any(props.get(k) != v for k, v in where.items()):
                    continue
                out.append(
                    {
                        "id": props.get("id"),
                        "scope": props.get("graph_scope", scope or "default"),
                        "labels": list(rec["labels"]),
                        "properties": props,
                    }
                )
        return out

    def query_relations(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        rel_type: str | None = None,
        scope: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        cypher = "MATCH (a)-[r]->(b) WHERE 1=1"
        params: dict[str, Any] = {"limit": limit}
        if source_id:
            cypher += " AND a.id = $src"
            params["src"] = source_id
        if target_id:
            cypher += " AND b.id = $tgt"
            params["tgt"] = target_id
        if rel_type:
            cypher += " AND type(r) = $rel"
            params["rel"] = self._safe_rel(rel_type)
        if scope:
            cypher += " AND coalesce(a.graph_scope, r.graph_scope) = $scope"
            params["scope"] = scope
        cypher += (
            " RETURN a.id AS source_id, b.id AS target_id, type(r) AS rel_type, "
            "properties(r) AS properties LIMIT $limit"
        )
        with self._driver.session() as session:
            return [
                {
                    "source_id": rec["source_id"],
                    "target_id": rec["target_id"],
                    "rel_type": rec["rel_type"],
                    "properties": dict(rec["properties"] or {}),
                    "scope": scope or "*",
                }
                for rec in session.run(cypher, **params)
            ]

    def stats(self, scope: str | None = None) -> dict[str, Any]:
        with self._driver.session() as session:
            if scope:
                n = session.run(
                    "MATCH (n {graph_scope:$s}) RETURN count(n) AS c", s=scope
                ).single()["c"]
                e = session.run(
                    "MATCH ()-[r]->() WHERE r.graph_scope = $s RETURN count(r) AS c",
                    s=scope,
                ).single()["c"]
            else:
                n = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                e = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        return {
            "backend": self.backend_name,
            "uri": self.uri,
            "nodes": n,
            "edges": e,
            "scope": scope or "*",
        }

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
            nid = str(node.get("id") or "")
            if not nid:
                continue
            self.upsert_node(
                nid,
                labels=node.get("labels") or ["Company"],
                properties=node.get("properties") or {},
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
        self._driver.close()

    @staticmethod
    def _safe_labels(labels: list[str]) -> list[str]:
        out = []
        for lab in labels:
            cleaned = "".join(c if c.isalnum() or c == "_" else "_" for c in lab)
            out.append(cleaned or "Entity")
        return out or ["Entity"]

    @staticmethod
    def _safe_rel(rel_type: str) -> str:
        cleaned = "".join(c if c.isalnum() or c == "_" else "_" for c in rel_type)
        return cleaned.upper() or "RELATED"

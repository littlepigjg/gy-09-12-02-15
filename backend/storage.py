"""存储层：使用 SQLite 持久化节点表与边表。

设计目标
--------
- 节点表 (nodes) 与边表 (edges) 分离，作为图数据的持久化来源。
- 边表对 source/target 建立索引，加速按节点取邻接边的查询。
- 所有写入走事务批量提交，导入大数据时避免逐条 commit 的开销。
"""

import sqlite3
import json
import os


class Storage:
    """基于 SQLite 的图持久化存储。"""

    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # 提升批量写入性能
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    id    TEXT PRIMARY KEY,
                    name  TEXT,
                    attrs TEXT
                );

                CREATE TABLE IF NOT EXISTS edges (
                    source TEXT,
                    target TEXT,
                    weight REAL DEFAULT 1.0,
                    PRIMARY KEY (source, target)
                );

                CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
                """
            )

    # ------------------------------------------------------------------ #
    # 写入
    # ------------------------------------------------------------------ #
    def clear(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM edges;")
            conn.execute("DELETE FROM nodes;")

    def add_node(self, node_id, name=None, attrs=None):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO nodes(id, name, attrs) VALUES (?, ?, ?)",
                (str(node_id), name or str(node_id), json.dumps(attrs or {}, ensure_ascii=False)),
            )

    def add_edge(self, source, target, weight=1.0):
        # 无向图：统一按 (min, max) 存储，避免重复边
        s, t = str(source), str(target)
        if s == t:
            return
        if s > t:
            s, t = t, s
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO edges(source, target, weight) VALUES (?, ?, ?)",
                (s, t, float(weight)),
            )

    def bulk_import(self, nodes, edges):
        """事务化批量导入节点与边。

        nodes: list[dict] -> {"id", "name"?, "attrs"?}
        edges: list[dict] -> {"source", "target", "weight"?}
        """
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO nodes(id, name, attrs) VALUES (?, ?, ?)",
                [
                    (
                        str(n["id"]),
                        n.get("name") or str(n["id"]),
                        json.dumps(n.get("attrs") or {}, ensure_ascii=False),
                    )
                    for n in nodes
                ],
            )
            edge_rows = []
            for e in edges:
                s, t = str(e["source"]), str(e["target"])
                if s == t:
                    continue
                if s > t:
                    s, t = t, s
                edge_rows.append((s, t, float(e.get("weight", 1.0))))
            conn.executemany(
                "INSERT OR REPLACE INTO edges(source, target, weight) VALUES (?, ?, ?)",
                edge_rows,
            )

    # ------------------------------------------------------------------ #
    # 读取
    # ------------------------------------------------------------------ #
    def get_all_nodes(self):
        with self._connect() as conn:
            rows = conn.execute("SELECT id, name, attrs FROM nodes;").fetchall()
        result = []
        for r in rows:
            try:
                attrs = json.loads(r["attrs"]) if r["attrs"] else {}
            except (json.JSONDecodeError, TypeError):
                attrs = {}
            result.append({"id": r["id"], "name": r["name"], "attrs": attrs})
        return result

    def get_all_edges(self):
        with self._connect() as conn:
            rows = conn.execute("SELECT source, target, weight FROM edges;").fetchall()
        return [{"source": r["source"], "target": r["target"], "weight": r["weight"]} for r in rows]

    def get_neighbors(self, node_id):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT source, target, weight FROM edges WHERE source = ? OR target = ?",
                (str(node_id), str(node_id)),
            ).fetchall()
        result = []
        for r in rows:
            nb = r["target"] if r["source"] == str(node_id) else r["source"]
            result.append({"node": nb, "weight": r["weight"]})
        return result

    def count_nodes(self):
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM nodes;").fetchone()[0]

    def count_edges(self):
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM edges;").fetchone()[0]

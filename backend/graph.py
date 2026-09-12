"""内存图结构：邻接表缓存。

优化要点
--------
- 图数据以邻接表 (dict[str, dict[str, float]]) 形式常驻内存，
  作为查询与图算法的统一入口，避免每次查询都回 SQLite。
- 邻接表只在导入数据后 rebuild 一次；对大数据集这是一次 O(V+E)
  的构建成本，之后所有遍历（BFS/PageRank/Louvain）均为 O(V+E) 级别的内存访问。
- 无向图按 (u->v, v->u) 双向存储，取邻居为 O(1)。
"""

from .storage import Storage


class Graph:
    def __init__(self, storage: Storage):
        self.storage = storage
        self.adj = {}      # 邻接表缓存: node_id -> {neighbor: weight}
        self.nodes = {}    # node_id -> {"name", "attrs"}
        self._communities = None  # 社群划分缓存，导入后惰性计算
        self.rebuild()

    # ------------------------------------------------------------------ #
    # 构建缓存
    # ------------------------------------------------------------------ #
    def rebuild(self):
        """从存储层重建邻接表缓存。"""
        self.adj = {}
        self.nodes = {}
        for n in self.storage.get_all_nodes():
            self.nodes[n["id"]] = {"name": n["name"], "attrs": n["attrs"]}
            self.adj.setdefault(n["id"], {})
        for e in self.storage.get_all_edges():
            s, t, w = e["source"], e["target"], e["weight"]
            self.adj.setdefault(s, {})
            self.adj.setdefault(t, {})
            self.adj[s][t] = w
            self.adj[t][s] = w
        self._communities = None

    def import_data(self, nodes, edges):
        """导入数据并重建缓存。"""
        self.storage.clear()
        self.storage.bulk_import(nodes, edges)
        self.rebuild()

    # ------------------------------------------------------------------ #
    # 基础查询
    # ------------------------------------------------------------------ #
    def has_node(self, node_id):
        return node_id in self.adj

    def neighbors(self, node_id):
        return dict(self.adj.get(node_id, {}))

    def node_count(self):
        return len(self.adj)

    def edge_count(self):
        return sum(len(nb) for nb in self.adj.values()) // 2

    def degree(self, node_id):
        return len(self.adj.get(node_id, {}))

    def node_ids(self):
        return list(self.adj.keys())

    def to_frontend(self):
        """导出为前端渲染所需的结构。"""
        nodes = [
            {"data": {"id": nid, "label": info["name"]}}
            for nid, info in self.nodes.items()
        ]
        edges = [
            {"data": {"id": f"{s}__{t}", "source": s, "target": t, "weight": w}}
            for s, nbs in self.adj.items()
            for t, w in nbs.items()
            if s < t  # 无向边只导出一次
        ]
        return {"nodes": nodes, "edges": edges}

    def stats(self):
        """图基础统计信息。"""
        v = self.node_count()
        e = self.edge_count()
        degrees = [len(nb) for nb in self.adj.values()]
        avg_degree = (sum(degrees) / v) if v else 0.0
        density = (2.0 * e / (v * (v - 1))) if v > 1 else 0.0
        return {
            "nodes": v,
            "edges": e,
            "avg_degree": round(avg_degree, 4),
            "density": round(density, 6),
            "max_degree": max(degrees) if degrees else 0,
            "isolated": sum(1 for d in degrees if d == 0),
        }

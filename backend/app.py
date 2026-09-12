"""Flask 后端服务：提供图查询 REST API 并托管前端静态资源。"""

import os
from flask import Flask, jsonify, request, send_from_directory

from .storage import Storage
from .graph import Graph
from . import algorithms
from .sample_data import generate_social_network

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "graph.db")

app = Flask(__name__, static_folder=None)

storage = Storage(DB_PATH)
graph = Graph(storage)


# ---------------------------------------------------------------------- #
# 前端页面
# ---------------------------------------------------------------------- #
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)


# ---------------------------------------------------------------------- #
# 图数据
# ---------------------------------------------------------------------- #
@app.route("/api/graph", methods=["GET"])
def api_graph():
    return jsonify(graph.to_frontend())


@app.route("/api/stats", methods=["GET"])
def api_stats():
    return jsonify(graph.stats())


@app.route("/api/import", methods=["POST"])
def api_import():
    """导入关系数据。支持 {nodes, edges} 或仅 {edges}（自动推断节点）。"""
    data = request.get_json(silent=True) or {}
    edges = data.get("edges", [])
    nodes = data.get("nodes", [])

    if not edges:
        return jsonify({"error": "缺少 edges 字段"}), 400

    # 若未显式提供 nodes，则从 edges 推断
    if not nodes:
        seen = {}
        for e in edges:
            for key in ("source", "target"):
                nid = str(e.get(key))
                if nid and nid not in seen:
                    seen[nid] = {"id": nid, "name": nid, "attrs": {}}
        nodes = list(seen.values())

    try:
        graph.import_data(nodes, edges)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"导入失败: {exc}"}), 400

    return jsonify({"ok": True, "stats": graph.stats()})


@app.route("/api/load_sample", methods=["POST"])
def api_load_sample():
    """生成并导入内置样例社交网络。"""
    body = request.get_json(silent=True) or {}
    nodes, edges = generate_social_network(
        n_communities=int(body.get("n_communities", 6)),
        nodes_per_community=int(body.get("nodes_per_community", 30)),
        p_in=float(body.get("p_in", 0.12)),
        p_out=float(body.get("p_out", 0.006)),
        seed=int(body.get("seed", 42)),
    )
    graph.import_data(nodes, edges)
    return jsonify({"ok": True, "stats": graph.stats()})


# ---------------------------------------------------------------------- #
# 图算法
# ---------------------------------------------------------------------- #
@app.route("/api/shortest_path", methods=["GET"])
def api_shortest_path():
    source = request.args.get("from")
    target = request.args.get("to")
    if not source or not target:
        return jsonify({"error": "需要 from 与 to 参数"}), 400

    path = algorithms.bfs_shortest_path(graph, source, target)
    if path is None:
        return jsonify({"error": "节点不存在或不可达", "path": None})
    return jsonify({"path": path, "length": len(path) - 1})


@app.route("/api/common_friends", methods=["GET"])
def api_common_friends():
    a = request.args.get("node1")
    b = request.args.get("node2")
    if not a or not b:
        return jsonify({"error": "需要 node1 与 node2 参数"}), 400

    friends = algorithms.common_friends(graph, a, b)
    return jsonify({"friends": friends, "count": len(friends)})


@app.route("/api/pagerank", methods=["GET"])
def api_pagerank():
    top_n = int(request.args.get("top_n", 10))
    ranks = algorithms.pagerank(graph)
    ranked = sorted(ranks.items(), key=lambda kv: kv[1], reverse=True)
    return jsonify(
        {
            "top": [
                {"node": node, "score": round(score, 6)}
                for node, score in ranked[:top_n]
            ]
        }
    )


@app.route("/api/communities", methods=["GET"])
def api_communities():
    """返回社群划分结果与每个节点所属社群。"""
    community = algorithms.louvain(graph)
    groups = algorithms.community_groups(community)
    return jsonify(
        {
            "community_count": len(groups),
            "node_community": community,
            "groups": {str(k): v for k, v in groups.items()},
        }
    )


@app.route("/api/neighbors", methods=["GET"])
def api_neighbors():
    node = request.args.get("node")
    if not node:
        return jsonify({"error": "需要 node 参数"}), 400
    nbs = graph.neighbors(node)
    return jsonify({"node": node, "neighbors": sorted(nbs.keys())})


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="社交网络分析服务")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    app.run(host=args.host, port=args.port, debug=False)

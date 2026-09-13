"""社群合并后处理的测试：默认一致性、两种控制方式、边界情况。"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import algorithms
from backend.sample_data import generate_social_network


class FakeGraph:
    """最小图结构，只提供算法需要的 adj 接口。"""

    def __init__(self, edges, nodes=None):
        self.adj = {}
        ids = set(nodes or [])
        for u, v, w in edges:
            ids.update([u, v])
        for nid in ids:
            self.adj.setdefault(nid, {})
        for u, v, w in edges:
            self.adj[u][v] = w
            self.adj[v][u] = w

    def node_ids(self):
        return list(self.adj.keys())

    def has_node(self, nid):
        return nid in self.adj


def sizes_of(community):
    groups = algorithms.community_groups(community)
    return {cid: len(m) for cid, m in groups.items()}


passed = []


def check(name, cond):
    assert cond, f"FAILED: {name}"
    passed.append(name)


# ---------------------------------------------------------------- 默认一致性
# 样例网络上，不传参数 / 显式传 None，结果必须与原始 Louvain 完全一致
nodes, edges = generate_social_network()
g = FakeGraph([(e["source"], e["target"], e["weight"]) for e in edges])
base = algorithms.louvain(g)
base_snapshot = dict(base)

out_default = algorithms.merge_small_communities(g, base)
check("默认(无参数)结果与原始 Louvain 完全一致", out_default == base_snapshot)
out_none = algorithms.merge_small_communities(g, base, max_communities=None, min_size=None)
check("显式 None 参数结果与原始 Louvain 完全一致", out_none == base_snapshot)
check("合并函数不修改调用方传入的划分", base == base_snapshot)

# 真实图结构走一遍 Graph 类（sqlite 临时库）
from backend.storage import Storage
from backend.graph import Graph
import tempfile

db = os.path.join(tempfile.mkdtemp(), "t.db")
graph = Graph(Storage(db))
graph.import_data(nodes, edges)
base2 = algorithms.louvain(graph)
check("Graph 类上默认结果一致",
      algorithms.merge_small_communities(graph, base2) == base2)

# ---------------------------------------------------------------- max_communities
merged = algorithms.merge_small_communities(g, base, max_communities=3)
check("max_communities=3 后社群数 <= 3", len(set(merged.values())) <= 3)
check("max_communities 后所有节点仍有归属", set(merged.keys()) == set(base.keys()))

# 限制个数 >= 实际社群数时不应有任何变化
n_comm = len(set(base.values()))
same = algorithms.merge_small_communities(g, base, max_communities=n_comm)
check("max_communities >= 实际社群数时结果不变", same == base_snapshot)
same2 = algorithms.merge_small_communities(g, base, max_communities=n_comm + 10)
check("max_communities 远大于实际社群数时结果不变", same2 == base_snapshot)

# max_communities=1 全部并为一个社群
one = algorithms.merge_small_communities(g, base, max_communities=1)
check("max_communities=1 收敛为单社群", len(set(one.values())) == 1)

# max_communities=0 / 负数按 1 处理
zero = algorithms.merge_small_communities(g, base, max_communities=0)
check("max_communities=0 按 1 处理", len(set(zero.values())) == 1)

# ---------------------------------------------------------------- min_size
merged_ms = algorithms.merge_small_communities(g, base, min_size=5)
sz = sizes_of(merged_ms)
check("min_size=5 后不存在小于 5 人的社群", all(s >= 5 for s in sz.values()))
check("min_size 后所有节点仍有归属", set(merged_ms.keys()) == set(base.keys()))

# min_size=1 不起任何作用（没有社群比 1 小）
same3 = algorithms.merge_small_communities(g, base, min_size=1)
check("min_size=1 时结果不变", same3 == base_snapshot)

# 两个参数同时用
both = algorithms.merge_small_communities(g, base, max_communities=4, min_size=5)
sz_both = sizes_of(both)
check("双参数：社群数 <= 4", len(sz_both) <= 4)
check("双参数：不存在小于 5 人的社群", all(s >= 5 for s in sz_both.values()))

# ---------------------------------------------------------------- 最近社群选择
# 小社群 s(2人) 与大社群 A(4人)、B(4人) 相连：
# s->A 边权 1.0，s->B 边权 5.0，应并入 B
g2 = FakeGraph([
    ("a1", "a2", 1.0), ("a2", "a3", 1.0), ("a3", "a4", 1.0), ("a1", "a3", 1.0),
    ("b1", "b2", 1.0), ("b2", "b3", 1.0), ("b3", "b4", 1.0), ("b1", "b3", 1.0),
    ("s1", "s2", 1.0),
    ("s1", "a1", 1.0),          # s -> A 权重 1
    ("s2", "b1", 5.0),          # s -> B 权重 5
])
comm2 = {"a1": 0, "a2": 0, "a3": 0, "a4": 0,
         "b1": 1, "b2": 1, "b3": 1, "b4": 1,
         "s1": 2, "s2": 2}
out2 = algorithms.merge_small_communities(g2, comm2, min_size=3)
check("小社群并入连接权重最大的社群(B)",
      out2["s1"] == out2["b1"] and out2["s2"] == out2["b1"])
check("A 社群不受影响", out2["a1"] == out2["a4"] != out2["b1"])

# ---------------------------------------------------------------- 孤立社群并入最大社群
# c_small 是孤立社群（无外部边），A 4 人、B 3 人，应并入 A
g3 = FakeGraph([
    ("a1", "a2", 1.0), ("a2", "a3", 1.0), ("a3", "a4", 1.0),
    ("b1", "b2", 1.0), ("b2", "b3", 1.0),
    ("x1", "x2", 1.0),   # x 社群内部有边但与外部无边
])
comm3 = {"a1": 0, "a2": 0, "a3": 0, "a4": 0,
         "b1": 1, "b2": 1, "b3": 1,
         "x1": 2, "x2": 2}
out3 = algorithms.merge_small_communities(g3, comm3, min_size=3)
check("孤立小社群并入规模最大的社群(A)",
      out3["x1"] == out3["a1"] and out3["x2"] == out3["a1"])

# ---------------------------------------------------------------- 边界：空网络
g_empty = FakeGraph([])
check("空网络：louvain 返回 {}", algorithms.louvain(g_empty) == {})
check("空网络：merge 返回 {}",
      algorithms.merge_small_communities(g_empty, {}, max_communities=3, min_size=5) == {})

# ---------------------------------------------------------------- 边界：只有一个社群
g_one = FakeGraph([("a", "b", 1.0), ("b", "c", 1.0)])
comm_one = {"a": 0, "b": 0, "c": 0}
out_one = algorithms.merge_small_communities(g_one, comm_one, max_communities=1, min_size=100)
check("单社群网络：结果不变", out_one == comm_one)

# ---------------------------------------------------------------- 边界：全是单点小社群
# 无边图：louvain 返回全部 0；直接构造每点一社群的划分测试 merge
g_iso = FakeGraph([], nodes=["n1", "n2", "n3", "n4", "n5"])
comm_iso = {f"n{i}": i for i in range(1, 6)}
out_iso = algorithms.merge_small_communities(g_iso, comm_iso, max_communities=2)
check("全单点社群：收敛到 2 个社群", len(set(out_iso.values())) == 2)
out_iso1 = algorithms.merge_small_communities(g_iso, comm_iso, max_communities=1)
check("全单点社群：max=1 收敛到 1 个", len(set(out_iso1.values())) == 1)
out_iso_ms = algorithms.merge_small_communities(g_iso, comm_iso, min_size=10)
check("全单点社群：min_size 大于所有社群时收敛到 1 个", len(set(out_iso_ms.values())) == 1)

# 有边但极稀疏：多个单点社群 + 一个大社群
g_sparse = FakeGraph([("a", "b", 1.0), ("b", "c", 1.0), ("a", "c", 1.0)],
                     nodes=["a", "b", "c", "s1", "s2", "s3"])
comm_sparse = {"a": 0, "b": 0, "c": 0, "s1": 1, "s2": 2, "s3": 3}
out_sparse = algorithms.merge_small_communities(g_sparse, comm_sparse, min_size=2)
check("稀疏图：单点全部并入大社群", len(set(out_sparse.values())) == 1)

# ---------------------------------------------------------------- 确定性与编号
r1 = algorithms.merge_small_communities(g, base, max_communities=3)
r2 = algorithms.merge_small_communities(g, base, max_communities=3)
check("合并结果确定可复现", r1 == r2)
check("合并后编号从 0 连续", sorted(set(r1.values())) == list(range(len(set(r1.values())))))

# 未触发合并时编号保持原样（不重新编号）
comm_gap = {"a": 5, "b": 5, "c": 9, "d": 9}
g_gap = FakeGraph([("a", "b", 1.0), ("c", "d", 1.0)])
out_gap = algorithms.merge_small_communities(g_gap, comm_gap, max_communities=2)
check("未触发合并时编号保持原样", out_gap == comm_gap)

print(f"全部 {len(passed)} 项测试通过：")
for name in passed:
    print(f"  ✓ {name}")

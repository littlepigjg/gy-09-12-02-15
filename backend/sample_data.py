"""生成带社群结构的合成社交网络数据。

使用随机块模型 (Stochastic Block Model)：
- 多个社群，社群内部连边概率高，社群之间连边概率低。
- 结果天然呈现清晰的社群结构，适合验证 Louvain 社群发现。
"""

import random


def generate_social_network(
    n_communities=6,
    nodes_per_community=30,
    p_in=0.12,
    p_out=0.006,
    seed=42,
):
    """生成节点表与边表。

    返回 (nodes, edges)，均为 list[dict]。
    """
    rng = random.Random(seed)
    nodes = []
    edges = []
    community_of = {}

    for c in range(n_communities):
        for i in range(nodes_per_community):
            nid = f"u{c}_{i}"
            nodes.append(
                {
                    "id": nid,
                    "name": nid,
                    "attrs": {"community": c, "group": c},
                }
            )
            community_of[nid] = c

    n = len(nodes)
    ids = [nd["id"] for nd in nodes]

    for a in range(n):
        for b in range(a + 1, n):
            p = p_in if community_of[ids[a]] == community_of[ids[b]] else p_out
            if rng.random() < p:
                edges.append(
                    {
                        "source": ids[a],
                        "target": ids[b],
                        "weight": round(rng.uniform(0.5, 2.0), 2),
                    }
                )

    # 确保每个节点至少有一条边（避免孤立点过多影响展示）
    degree = {nid: 0 for nid in ids}
    for e in edges:
        degree[e["source"]] += 1
        degree[e["target"]] += 1
    for nid, d in degree.items():
        if d == 0:
            # 连到同社群随机节点
            same = [x for x in ids if x != nid and community_of[x] == community_of[nid]]
            t = rng.choice(same) if same else rng.choice([x for x in ids if x != nid])
            edges.append({"source": nid, "target": t, "weight": 1.0})

    return nodes, edges

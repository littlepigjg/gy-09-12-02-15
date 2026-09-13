"""图算法：BFS 最短路径、共同好友、简化 PageRank、简化 Louvain 社群发现。

所有算法均直接读取内存中的邻接表缓存（Graph.adj），
不访问数据库，保证在大规模图上的内存级高效执行。
"""

from collections import deque


def bfs_shortest_path(graph, source, target):
    """广度优先搜索求无权图最短路径。

    返回路径节点列表（含首尾），不可达返回 None。
    时间复杂度 O(V + E)。
    """
    source, target = str(source), str(target)
    if not graph.has_node(source) or not graph.has_node(target):
        return None
    if source == target:
        return [source]

    visited = {source}
    prev = {source: None}
    queue = deque([source])

    while queue:
        cur = queue.popleft()
        if cur == target:
            break
        for nb in graph.adj.get(cur, {}):
            if nb not in visited:
                visited.add(nb)
                prev[nb] = cur
                queue.append(nb)

    if target not in visited:
        return None

    path = []
    node = target
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()
    return path


def common_friends(graph, a, b):
    """求两个节点的共同好友（共同邻居）。

    基于邻接表集合求交集，O(min(deg(a), deg(b)))。
    """
    a, b = str(a), str(b)
    if not graph.has_node(a) or not graph.has_node(b):
        return []
    return sorted(set(graph.adj.get(a, {})) & set(graph.adj.get(b, {})))


def pagerank(graph, damping=0.85, epsilon=1e-6, max_iter=100):
    """简化 PageRank（幂迭代法）。

    将无向图视为双向图，按出度均分权重。
    时间复杂度 O(iter * E)。
    """
    nodes = graph.node_ids()
    n = len(nodes)
    if n == 0:
        return {}

    ranks = {node: 1.0 / n for node in nodes}

    for _ in range(max_iter):
        base = (1.0 - damping) / n
        new_ranks = {node: base for node in nodes}
        for node in nodes:
            nbs = graph.adj.get(node, {})
            if not nbs:
                # 悬挂节点：权重均匀回流到所有节点
                share = ranks[node] / n
                for other in nodes:
                    new_ranks[other] += damping * share
            else:
                share = ranks[node] / len(nbs)
                for nb in nbs:
                    new_ranks[nb] += damping * share

        delta = sum(abs(new_ranks[node] - ranks[node]) for node in nodes)
        ranks = new_ranks
        if delta < epsilon:
            break

    return ranks


def _local_moving(cur_nodes, weight, deg, m, comm, tot, max_passes):
    """单层局部移动：将每个节点移动到使模块度增益最大的邻居社区。

    返回本次移动是否改进了划分。
    """
    moved_any = False
    for _ in range(max_passes):
        moved = False
        for u in cur_nodes:
            cu = comm[u]

            # 统计 u 与各邻居社区的连接权重（不含自环）
            w_to = {}
            for v, w in weight[u].items():
                c = comm[v]
                w_to[c] = w_to.get(c, 0.0) + w

            # 从当前社区移除 u
            tot[cu] -= deg[u]

            best_c = cu
            best_gain = 0.0
            for c, k_uin in w_to.items():
                gain = k_uin / m - tot[c] * deg[u] / (2.0 * m * m)
                if gain > best_gain:
                    best_gain = gain
                    best_c = c

            # 将 u 加入最佳社区
            comm[u] = best_c
            tot[best_c] += deg[u]

            if best_c != cu:
                moved = True

        if not moved:
            break
        moved_any = True
    return moved_any


def louvain(graph, max_levels=20, max_passes=20):
    """Louvain 社群发现（局部移动 + 社区聚合两阶段迭代）。

    在加权无向图上多层级执行：
    1. 局部移动：每个节点初始独立成社区，按模块度增益
       ΔQ = k_i,in / m - Σ_tot * k_i / (2m^2) 反复移动节点。
    2. 社区聚合：将每个社区收缩为一个超节点，形成更粗粒度的图，
       再递归执行局部移动。

    相比完整实现省略了部分优化（如随机化节点顺序、模块度阈值早停），
    但保留了两阶段核心结构，可稳定得到合理的社群划分。
    """
    nodes = graph.node_ids()
    if not nodes:
        return {}

    adj = graph.adj
    m2 = sum(sum(w for w in adj[u].values()) for u in nodes)
    if m2 == 0:
        return {u: 0 for u in nodes}
    m = m2 / 2.0

    # 当前层级的超节点（初始为原始节点）
    cur_nodes = list(nodes)
    # 原始节点 -> 当前超节点
    node_to_super = {u: u for u in nodes}

    # 当前层级的加权图表示
    weight = {u: dict(adj[u]) for u in cur_nodes}          # 节点间边权（无自环）
    self_w = {u: 0.0 for u in cur_nodes}                   # 自环权（社区内部边权）
    deg = {u: sum(adj[u].values()) for u in cur_nodes}     # 总度数

    for _ in range(max_levels):
        # ---- 局部移动 ----
        comm = {u: i for i, u in enumerate(cur_nodes)}
        tot = {i: deg[u] for i, u in enumerate(cur_nodes)}
        improved = _local_moving(cur_nodes, weight, deg, m, comm, tot, max_passes)

        # 若未能进一步合并，则停止
        if not improved or len(set(comm.values())) == len(cur_nodes):
            break

        # ---- 社区聚合 ----
        mapping = {}
        for u in cur_nodes:
            c = comm[u]
            if c not in mapping:
                mapping[c] = len(mapping)
        new_nodes = list(range(len(mapping)))

        new_weight = {c: {} for c in new_nodes}
        new_self = {c: 0.0 for c in new_nodes}
        new_deg = {c: 0.0 for c in new_nodes}

        # 聚合自环与总度数
        for u in cur_nodes:
            c = mapping[comm[u]]
            new_self[c] += self_w[u]
            new_deg[c] += deg[u]

        # 聚合节点间边（每条无向边只统计一次）
        seen = set()
        for u in cur_nodes:
            cu = mapping[comm[u]]
            for v, w in weight[u].items():
                pair = (u, v) if u <= v else (v, u)
                if pair in seen:
                    continue
                seen.add(pair)
                cv = mapping[comm[v]]
                if cu == cv:
                    new_self[cu] += w
                else:
                    new_weight[cu][cv] = new_weight[cu].get(cv, 0.0) + w
                    new_weight[cv][cu] = new_weight[cv].get(cu, 0.0) + w

        # 更新「原始节点 -> 超节点」映射，进入下一层级
        for o in nodes:
            node_to_super[o] = mapping[comm[node_to_super[o]]]
        cur_nodes = new_nodes
        weight = new_weight
        self_w = new_self
        deg = new_deg

    # 将最终划分映射回原始节点并压缩编号
    final_comm = {u: comm[node_to_super[u]] for u in nodes}
    mapping = {}
    result = {}
    for u in nodes:
        c = final_comm[u]
        if c not in mapping:
            mapping[c] = len(mapping)
        result[u] = mapping[c]
    return result


def community_groups(community):
    """将 {node: community_id} 转换为 {community_id: [nodes]}。"""
    groups = {}
    for node, cid in community.items():
        groups.setdefault(cid, []).append(node)
    return groups


def _nearest_community(graph, community, groups, source, sizes):
    """为待合并社群 source 选择目标社群。

    优先并入与 source 之间边权总和最大的社群（"离得最近"）；
    若 source 没有任何外部连边（如孤立点组成的社群），
    则并入当前规模最大的社群。
    平局一律按社群编号升序裁决，保证结果确定可复现。
    """
    weights = {}
    for node in groups[source]:
        for nb, w in graph.adj.get(node, {}).items():
            c = community.get(nb)
            if c is None or c == source:
                continue
            weights[c] = weights.get(c, 0.0) + w
    if weights:
        # 连接权重降序 -> 对方规模降序 -> 编号升序
        return max(weights, key=lambda c: (weights[c], sizes[c], -c))
    # 孤立社群：并入规模最大的社群（平局取编号小者）
    return max((c for c in groups if c != source), key=lambda c: (sizes[c], -c))


def _relabel_by_size(community, groups):
    """按社群规模降序重新编号（最大社群为 0），平局按原编号升序。"""
    order = sorted(groups, key=lambda c: (-len(groups[c]), c))
    new_id = {c: i for i, c in enumerate(order)}
    return {node: new_id[cid] for node, cid in community.items()}


def merge_small_communities(graph, community, max_communities=None, min_size=None):
    """社群划分后处理：将零散小社群并入"离得最近"的社群。

    两种触发条件（可单独或同时使用）：
    - max_communities: 限定最终社群个数，超出时从最小社群开始逐轮合并；
    - min_size: 规模小于该值的社群被合并。

    两个参数均为 None（默认）时不做任何处理、原样返回，
    保证不调整参数时划分结果与原始 Louvain 输出完全一致。
    每轮合并当前规模最小的社群（平局取编号小者），目标社群由
    _nearest_community 按连接强度选出；整个过程确定可复现。
    只有实际发生过合并时才重新压缩编号，未合并时编号保持原样。
    """
    if not community or (max_communities is None and min_size is None):
        return community

    groups = community_groups(community)
    if len(groups) <= 1:
        # 空网络或只有一个社群：无可合并
        return community

    # 拷贝，避免改动调用方持有的原始划分
    community = dict(community)
    groups = {cid: list(members) for cid, members in groups.items()}

    limit = max(1, int(max_communities)) if max_communities is not None else None

    merged_any = False
    while len(groups) > 1:
        sizes = {cid: len(members) for cid, members in groups.items()}
        too_small = min_size is not None and min(sizes.values()) < min_size
        too_many = limit is not None and len(groups) > limit
        if not (too_small or too_many):
            break

        smallest = min(sizes, key=lambda c: (sizes[c], c))
        target = _nearest_community(graph, community, groups, smallest, sizes)

        for node in groups[smallest]:
            community[node] = target
        groups[target].extend(groups.pop(smallest))
        merged_any = True

    if merged_any:
        community = _relabel_by_size(community, groups)
    return community

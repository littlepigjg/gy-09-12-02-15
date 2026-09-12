// 社交网络分析服务前端（Vue 3 + Cytoscape.js）

const PALETTE = [
  "#4c8dff", "#37d0a0", "#ff6b81", "#ffa94d", "#b197fc", "#f783ac",
  "#66d9e8", "#e9c46a", "#8ce99a", "#ff8787", "#74c0fc", "#d0bfff",
  "#ffd43b", "#63e6be", "#faa2c1", "#a9e34b",
];

function edgeKey(a, b) {
  return a < b ? `${a}__${b}` : `${b}__${a}`;
}

const { createApp } = Vue;

const app = createApp({
  data() {
    return {
      loading: false,
      stats: null,
      nodeIds: [],
      importText: "",
      pathFrom: "",
      pathTo: "",
      pathResult: "",
      cfA: "",
      cfB: "",
      commonResult: "",
      pagerankTop: 10,
      pagerankList: [],
      communityInfo: null,
      communityColors: {},
      hasGraph: false,
    };
  },

  mounted() {
    this.cy = cytoscape({
      container: this.$refs.cyRef,
      style: this.buildStyle(),
      layout: {
        name: "cose",
        animate: false,
        padding: 40,
        nodeRepulsion: 8000,
        idealEdgeLength: 70,
        gravity: 0.25,
      },
      minZoom: 0.1,
      maxZoom: 4,
    });
  },

  methods: {
    buildStyle() {
      return [
        {
          selector: "node",
          style: {
            "background-color": "#8b96ab",
            label: "data(label)",
            "font-size": 6,
            color: "#dbe4f0",
            "text-valign": "center",
            "text-halign": "right",
            "text-margin-x": 4,
            width: 12,
            height: 12,
            "border-width": 1,
            "border-color": "#0f1420",
            "transition-property": "opacity, border-width, width, height",
            "transition-duration": "0.2s",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1,
            "line-color": "#3a4560",
            "curve-style": "haystack",
            opacity: 0.55,
            "transition-property": "opacity, width, line-color",
            "transition-duration": "0.2s",
          },
        },
        {
          selector: "node.highlight",
          style: {
            "border-width": 3,
            "border-color": "#ffd43b",
            width: 22,
            height: 22,
            "z-index": 999,
            "font-size": 9,
          },
        },
        {
          selector: "edge.highlight",
          style: {
            width: 4,
            "line-color": "#ffd43b",
            opacity: 1,
          },
        },
        {
          selector: ".dim",
          style: { opacity: 0.08 },
        },
      ];
    },

    async api(url, options = {}) {
      const resp = await fetch(url, options);
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data.error || `请求失败 (${resp.status})`);
      }
      return data;
    },

    async loadSample() {
      this.loading = true;
      try {
        await this.api("/api/load_sample", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        await this.refresh();
      } catch (e) {
        alert("加载样例失败: " + e.message);
      } finally {
        this.loading = false;
      }
    },

    async importData() {
      if (!this.importText.trim()) {
        alert("请先粘贴 JSON 数据");
        return;
      }
      let payload;
      try {
        payload = JSON.parse(this.importText);
      } catch (e) {
        alert("JSON 解析失败: " + e.message);
        return;
      }
      this.loading = true;
      try {
        await this.api("/api/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        await this.refresh();
      } catch (e) {
        alert("导入失败: " + e.message);
      } finally {
        this.loading = false;
      }
    },

    async refresh() {
      const [graphData, communityData, stats] = await Promise.all([
        this.api("/api/graph"),
        this.api("/api/communities"),
        this.api("/api/stats"),
      ]);

      this.stats = stats;
      this.communityInfo = communityData;
      this.hasGraph = graphData.nodes.length > 0;

      // 建立社群颜色映射
      const colors = {};
      const colorSet = new Set();
      Object.values(communityData.node_community).forEach((c) => colorSet.add(c));
      [...colorSet].sort((a, b) => a - b).forEach((c, i) => {
        colors[c] = PALETTE[i % PALETTE.length];
      });
      this.communityColors = colors;

      // 重建图元素
      this.cy.elements().remove();
      this.cy.add(graphData.nodes.concat(graphData.edges));

      // 社群着色
      this.cy.nodes().forEach((node) => {
        const cid = communityData.node_community[node.id()];
        node.style("background-color", colors[cid] || "#8b96ab");
      });

      this.nodeIds = graphData.nodes.map((n) => n.data.id).sort();
      this.clearHighlight();
      this.cy.fit(undefined, 30);
    },

    async findPath() {
      const { path } = await this.api(
        `/api/shortest_path?from=${encodeURIComponent(this.pathFrom)}&to=${encodeURIComponent(this.pathTo)}`
      );
      if (!path) {
        this.pathResult = "不可达";
        this.clearHighlight();
        return;
      }
      this.pathResult = `${path.length - 1} 步: ${path.join(" -> ")}`;
      this.highlightPath(path);
    },

    highlightPath(path) {
      this.cy.elements().removeClass("highlight dim");
      this.cy.elements().addClass("dim");

      const pathNodes = new Set(path);
      const pathEdges = new Set();
      for (let i = 0; i < path.length - 1; i++) {
        pathEdges.add(edgeKey(path[i], path[i + 1]));
      }

      const els = this.cy.collection();
      pathNodes.forEach((id) => {
        const n = this.cy.getElementById(id);
        if (n.length) els.merge(n);
      });
      pathEdges.forEach((id) => {
        const e = this.cy.getElementById(id);
        if (e.length) els.merge(e);
      });

      els.removeClass("dim").addClass("highlight");
      this.cy.fit(els, 60);
    },

    async findCommonFriends() {
      const { friends } = await this.api(
        `/api/common_friends?node1=${encodeURIComponent(this.cfA)}&node2=${encodeURIComponent(this.cfB)}`
      );
      this.commonResult = friends.length
        ? `共 ${friends.length} 个: ${friends.join(", ")}`
        : "无共同好友";
    },

    async runPagerank() {
      const { top } = await this.api(`/api/pagerank?top_n=${this.pagerankTop}`);
      this.pagerankList = top;
    },

    async detectCommunities() {
      const data = await this.api("/api/communities");
      this.communityInfo = data;

      const colors = {};
      const colorSet = new Set(Object.values(data.node_community));
      [...colorSet].sort((a, b) => a - b).forEach((c, i) => {
        colors[c] = PALETTE[i % PALETTE.length];
      });
      this.communityColors = colors;

      this.cy.nodes().forEach((node) => {
        const cid = data.node_community[node.id()];
        node.style("background-color", colors[cid] || "#8b96ab");
      });
    },

    clearHighlight() {
      this.cy.elements().removeClass("highlight dim");
      this.pathResult = "";
      this.commonResult = "";
    },
  },
});

app.mount("#app");

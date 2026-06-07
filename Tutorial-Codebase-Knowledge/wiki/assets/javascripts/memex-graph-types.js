const memexActiveTypes = new Set();

function memexNodeType(label) {
  if (!label) return "neutral";

  const hidden = new Set([
    "index",
    "log",
    "theme-source-documents",
    "theme-building-entity",
    "theme-place-entity",
    "theme-associative-trail",
    "existing-building-source-set"
  ]);

  if (hidden.has(label) || label.startsWith("theme-theme-")) return "hidden";
  if (label.startsWith("source-")) return "source";
  if (label.startsWith("theme-") || label === "arts-and-crafts") return "theme";
  if (label.startsWith("place-") || label.endsWith("-buildings") || label.includes("source-set")) return "collection";
  if (label.includes("street") || label.includes("lane")) return "street";
  if (["farnham", "compton", "surrey", "guildford", "brighton", "hardham", "clayton", "coombes"].includes(label)) return "place";
  return "building";
}

function memexClassifyGraph() {
  const connectedLabels = new Set();

  if (memexActiveTypes.size) {
    document.querySelectorAll(".links .link").forEach(link => {
      const d = link.__data__ || {};
      const sourceLabel = d.source?.name || d.source?.id || d.source || "";
      const targetLabel = d.target?.name || d.target?.id || d.target || "";
      const sourceType = memexNodeType(String(sourceLabel));
      const targetType = memexNodeType(String(targetLabel));

      if (memexActiveTypes.has(sourceType)) connectedLabels.add(String(targetLabel));
      if (memexActiveTypes.has(targetType)) connectedLabels.add(String(sourceLabel));
    });
  }

  document.querySelectorAll(".nodes .node").forEach(node => {
    const label = node.querySelector("text")?.textContent?.trim() || "";
    const type = memexNodeType(label);

    node.classList.remove(
      "node--building", "node--place", "node--street", "node--theme",
      "node--source", "node--collection", "node--neutral", "node--hidden",
      "node--filtered", "node--connected"
    );

    node.classList.add(`node--${type}`);

    if (memexActiveTypes.size && !node.classList.contains("current")) {
      if (memexActiveTypes.has(type)) return;
      else if (connectedLabels.has(label)) node.classList.add("node--connected");
      else node.classList.add("node--filtered");
    }
  });

  document.querySelectorAll(".links .link").forEach(link => {
    const d = link.__data__ || {};
    const sourceLabel = d.source?.name || d.source?.id || d.source || "";
    const targetLabel = d.target?.name || d.target?.id || d.target || "";
    const sourceType = memexNodeType(String(sourceLabel));
    const targetType = memexNodeType(String(targetLabel));

    link.classList.remove("edge--hidden", "edge--filtered");

    if (sourceType === "hidden" || targetType === "hidden") {
      link.classList.add("edge--hidden");
    }

    if (memexActiveTypes.size && !memexActiveTypes.has(sourceType) && !memexActiveTypes.has(targetType)) {
      link.classList.add("edge--filtered");
    }
  });

  memexAddLegend();
  memexUpdateLegendState();
}

function memexApplyVisibleForce() {
  if (!window.d3) return;

  const graph = document.querySelector(".modal_graph svg") || document.querySelector(".graph svg");
  if (!graph) return;

  const width = graph.clientWidth || 900;
  const height = graph.clientHeight || 500;

  const nodeEls = [...document.querySelectorAll(".nodes .node")]
    .filter(n => !n.classList.contains("node--hidden") && !n.classList.contains("node--filtered"));

  const nodes = nodeEls.map(el => el.__data__).filter(Boolean);
  const visibleIds = new Set(nodes.map(n => n.id));

  const links = [...document.querySelectorAll(".links .link")]
    .filter(l => !l.classList.contains("edge--hidden") && !l.classList.contains("edge--filtered"))
    .map(l => l.__data__)
    .filter(Boolean)
    .filter(l => visibleIds.has(l.source?.id || l.source) && visibleIds.has(l.target?.id || l.target));

  nodes.forEach(n => {
    if (n.id && document.querySelector(`.nodes .node.current`)?.__data__?.id === n.id) {
      n.fx = width / 2;
      n.fy = height / 2;
    } else {
      n.fx = null;
      n.fy = null;
    }
  });

  const simulation = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id(d => d.id).distance(95))
    .force("charge", d3.forceManyBody().strength(-420))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collide", d3.forceCollide(22))
    .alpha(1)
    .restart();

  simulation.on("tick", () => {
    document.querySelectorAll(".nodes .node").forEach(el => {
      const d = el.__data__;
      if (d && visibleIds.has(d.id)) el.setAttribute("transform", `translate(${d.x},${d.y})`);
    });

    document.querySelectorAll(".links .link").forEach(el => {
      const d = el.__data__;
      if (!d) return;
      const s = d.source;
      const t = d.target;
      if (!s || !t || !visibleIds.has(s.id || s) || !visibleIds.has(t.id || t)) return;

      el.setAttribute("x1", s.x);
      el.setAttribute("y1", s.y);
      el.setAttribute("x2", t.x);
      el.setAttribute("y2", t.y);
    });
  });
}

function memexAddLegend() {
  document.querySelectorAll(".graph, .modal_graph").forEach(graph => {
    if (graph.querySelector(".memex-graph-legend")) return;

    const legend = document.createElement("div");
    legend.className = "memex-graph-legend";
    legend.innerHTML = `
      <button type="button" data-type="building"><b class="legend-building"></b>Building</button>
      <button type="button" data-type="place"><b class="legend-place"></b>Place</button>
      <button type="button" data-type="street"><b class="legend-street"></b>Street</button>
      <button type="button" data-type="theme"><b class="legend-theme"></b>Theme</button>
      <button type="button" data-type="source"><b class="legend-source"></b>Source</button>
      <button type="button" data-type="collection"><b class="legend-collection"></b>Collection</button>
      <button type="button" data-type="">All</button>
      <button type="button" data-action="layout">Apply layout</button>
    `;

    legend.querySelectorAll("button").forEach(btn => {
      btn.addEventListener("click", event => {
        event.preventDefault();
        event.stopPropagation();

        if (btn.dataset.action === "layout") {
          memexApplyVisibleForce();
          return;
        }

        const type = btn.dataset.type || "";
        if (!type) memexActiveTypes.clear();
        else if (memexActiveTypes.has(type)) memexActiveTypes.delete(type);
        else memexActiveTypes.add(type);

        memexClassifyGraph();
      });
    });

    graph.appendChild(legend);
  });
}

function memexUpdateLegendState() {
  document.querySelectorAll(".memex-graph-legend button").forEach(btn => {
    const type = btn.dataset.type || "";
    btn.classList.toggle("active", type ? memexActiveTypes.has(type) : memexActiveTypes.size === 0);
  });
}

new MutationObserver(memexClassifyGraph).observe(document.body, { childList: true, subtree: true });
document.addEventListener("DOMContentLoaded", memexClassifyGraph);
setInterval(memexClassifyGraph, 500);

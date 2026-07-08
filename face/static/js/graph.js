window.renderGraph = function renderGraph(graphData) {
  const svg = d3.select("#graph-svg");
  svg.selectAll("*").remove();

  const width = svg.node().clientWidth || 800;
  const height = +svg.attr("height") || 360;

  const nodes = graphData.nodes.map((n) => ({ ...n }));
  const links = graphData.edges.map((e) => ({ source: e.source, target: e.target }));

  const simulation = d3
    .forceSimulation(nodes)
    .force(
      "link",
      d3
        .forceLink(links)
        .id((d) => d.id)
        .distance(80)
    )
    .force("charge", d3.forceManyBody().strength(-120))
    .force("center", d3.forceCenter(width / 2, height / 2));

  const link = svg
    .append("g")
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("class", "graph-link");

  const node = svg
    .append("g")
    .selectAll("circle")
    .data(nodes)
    .join("circle")
    .attr("class", "graph-node")
    .attr("r", 6);

  const label = svg
    .append("g")
    .selectAll("text")
    .data(nodes)
    .join("text")
    .attr("class", "graph-label")
    .attr("dx", 9)
    .attr("dy", 3)
    .text((d) => d.label);

  simulation.on("tick", () => {
    link
      .attr("x1", (d) => d.source.x)
      .attr("y1", (d) => d.source.y)
      .attr("x2", (d) => d.target.x)
      .attr("y2", (d) => d.target.y);

    node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
    label.attr("x", (d) => d.x).attr("y", (d) => d.y);
  });
};

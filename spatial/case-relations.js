function initializeCaseRelations({rows, modes, hasMetres, areaValue, calibration, readableArea, canCompare, chooseCase, comparisonUrl}) {
  const section = document.querySelector(".case-relations");
  const drawing = section.querySelector("svg");
  const buttons = [...section.querySelectorAll(".case-relations-questions [data-relation-question]")];
  const clearButton = section.querySelector(".case-relations-clear");
  const status = section.querySelector(".case-relations-status");
  const byId = new Map(rows.map(row => [row.case, row]));
  const area = (row, key) => areaValue(row, key + "_area_m2");
  const display = (row, key) => readableArea(row, key + "_area_m2");
  const radius = value => 7.1 * Math.sqrt(Math.max(0, value));
  const columns = [
    {mode:"human-led", title:"Human-led", x:212, drift:[0,-12,5,9,-5], waists:[.55,.20,.74,.38]},
    {mode:"robotic-assembly", title:"Robot-led", x:515, drift:[0,10,2,-10,7], waists:[.23,.62,.32,.55]},
    {mode:"human-robot", title:"Mixed", x:824, drift:[10,2,-2,7,15], waists:[.41,.85,.33,.62]}
  ];
  const nodes = new Map();
  let question = "all";

  function svg(tag, attributes = {}, content) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (content !== undefined) element.textContent = content;
    return element;
  }

  const defs = svg("defs");
  const grid = svg("pattern", {id:"case-grid", width:28, height:28, patternUnits:"userSpaceOnUse"});
  grid.append(svg("path", {d:"M 0 28 V 0 H 28", fill:"none", stroke:"#e7efe9"}));
  defs.append(grid);
  drawing.append(defs, svg("rect", {x:14,y:58,width:932,height:691,fill:"url(#case-grid)","aria-hidden":"true"}));
  const outlines = svg("g", {"aria-hidden":"true"});
  const lines = svg("g", {"aria-hidden":"true"});
  const markers = svg("g");
  drawing.append(outlines, lines, markers);

  function band(points, waists) {
    const anchors = points.flatMap((point, index) => {
      const next = points[index + 1];
      const anchor = {x:point.x, y:point.y, w:point.r + 8};
      if (!next) return [anchor];
      return [anchor, {x:(point.x + next.x)/2, y:(point.y + next.y)/2,
        w:Math.max(5, Math.min(point.r, next.r) * waists[index])}];
    });
    const first = anchors[0];
    const last = anchors.at(-1);
    const left = [];
    const right = [];
    for (let index = 0; index < anchors.length - 1; index++) {
      const a = anchors[index];
      const b = anchors[index + 1];
      for (let step = 0; step < 28; step++) {
        const t = step / 28;
        const smooth = t*t*(3 - 2*t);
        const y = a.y + (b.y - a.y)*t;
        const x = a.x + (b.x - a.x)*smooth;
        const w = a.w + (b.w - a.w)*smooth;
        let low = x - w;
        let high = x + w;
        for (const point of points) {
          const section = (point.r + 4)**2 - (y - point.y)**2;
          if (section <= 0) continue;
          const span = Math.sqrt(section);
          low = Math.min(low, point.x - span);
          high = Math.max(high, point.x + span);
        }
        left.push(`${low.toFixed(2)} ${y.toFixed(2)}`);
        right.push(`${high.toFixed(2)} ${y.toFixed(2)}`);
      }
    }
    return `M ${first.x - first.w} ${first.y} L ${left.join(" L ")} L ${last.x - last.w} ${last.y}` +
      ` A ${last.w} ${last.w + 4} 0 0 0 ${last.x + last.w} ${last.y} L ${right.reverse().join(" L ")}` +
      ` A ${first.w} ${first.w + 4} 0 0 0 ${first.x - first.w} ${first.y} Z`;
  }

  for (const column of columns) {
    const ids = modes.find(mode => mode.mode === column.mode)?.cases || [];
    const points = ids.map(id => byId.get(id)).filter(Boolean).map((row, index) => ({row,
      x:column.x + (column.drift[index] || 0), y:123 + index*137,
      r:hasMetres(row) ? radius(area(row,"activity")) : 0}));
    outlines.append(svg("text", {x:column.x-175,y:36,class:"case-mode-title"}, column.title));
    if (points.length) outlines.append(svg("path", {d:band(points,column.waists),class:"case-band"}));
    for (const point of points) {
      const {row, x, y, r} = point;
      const labelX = column.x - 175;
      const caseLabel = row.case + (calibration(row) ? " ≈" : "");
      const comparable = canCompare(row);
      const group = svg("g", {role:comparable ? "button" : "link",tabindex:"0","data-atlas-case":row.case,
        "aria-label":comparable ? `${row.case}, ${column.title}. F ${display(row,"object")}, A ${display(row,"activity")}, human ${display(row,"human")}, machine ${display(row,"machine")}` :
          `${row.case}, ${column.title}. Open the case sheet.`});
      if (comparable) group.setAttribute("aria-pressed", "false");
      group.append(svg("circle", {cx:x,cy:y,r:Math.max(50,r),class:"case-hit"}));
      group.append(svg("rect", {x:labelX-8,y:y-37,width:111,height:76,class:"case-hit"}));
      group.append(svg("rect", {x:labelX-5,y:y-30,width:103,height:57,class:"case-label-paper"}));
      group.append(svg("text", {x:labelX,y:y-8,class:"case-node-label"}, caseLabel));
      const short = key => area(row,key).toFixed(1);
      if (hasMetres(row)) {
        const areaLabel = svg("text", {x:labelX,y:y+11,class:"case-node-values"});
        areaLabel.append(svg("tspan", {}, `A ${short("activity")}`),
          svg("tspan", {dx:8,class:"case-value-footprint"}, `F ${short("object")}`));
        const rolesLabel = svg("text", {x:labelX,y:y+25,class:"case-node-values"});
        rolesLabel.append(svg("tspan", {class:"case-value-human"}, `H ${short("human")}`),
          svg("tspan", {dx:8,class:"case-value-machine"}, `R ${short("machine")}`));
        group.append(areaLabel, rolesLabel);
      }
      if (r) {
        const layers = [["object","footprint",0],["human","human",-1],["machine","machine",1]]
          .map(([key, name, sign]) => ({name, sign, extent:radius(area(row,key))}))
          .filter(layer => layer.extent > 0)
          .sort((a,b) => b.extent-a.extent);
        for (const {name, sign, extent} of layers) {
          const gap = Math.max(0,r-extent);
          group.append(svg("circle", {cx:x+sign*.75*gap,cy:y-sign*.13*gap,r:extent,class:`case-node-${name}`}));
        }
      }
      group.append(svg("circle", {cx:x,cy:y,r:r || 8,class:"case-node-activity"}));
      group.append(svg("circle", {cx:x,cy:y,r:Math.max(12,r)+7,class:"case-node-focus"}));
      group.addEventListener("click", () => chooseCase(row.case));
      group.addEventListener("keydown", event => {
        if (event.key !== " " && event.key !== "Enter") return;
        event.preventDefault();
        chooseCase(row.case);
      });
      markers.append(group);
      nodes.set(row.case, {...point, element:group});
    }
  }

  const pairs = {
    spread:[["V01","V24"]],
    roles:[["V20","V22"], ["V04","V28"]],
    parts:[["V27","V29"]]
  };
  function relationFor(ids, topic) {
    const [a,b] = ids.map(id => byId.get(id));
    if (!a || !b || ![a,b].every(hasMetres)) return null;
    const similar = (key, threshold) => {
      const [x,y] = [area(a,key),area(b,key)];
      return Math.max(x,y) > 0 && Math.abs(x-y) <= threshold*Math.max(x,y);
    };
    let matched = false;
    if (topic === "spread" && similar("object",.20)) {
      const sizes = [area(a,"activity"),area(b,"activity")];
      const ratio = Math.max(...sizes) / Math.min(...sizes);
      matched = Number.isFinite(ratio) && ratio >= 1.5;
    }
    if (topic === "roles" && similar("object",.20) && similar("activity",.15)) {
      matched = true;
    }
    if (topic === "parts" && similar("part",.15)) {
      matched = true;
    }
    return matched;
  }

  function curve(a,b) {
    if (Math.abs(a.x-b.x) < 85) {
      const start = a.x+a.r+5;
      const end = b.x+b.r+5;
      const edge = Math.max(start,end)+75;
      return `M ${start} ${a.y} C ${edge} ${a.y} ${edge} ${b.y} ${end} ${b.y}`;
    }
    const direction = Math.sign(b.x-a.x);
    const start = a.x+direction*(a.r+4);
    const end = b.x-direction*(b.r+4);
    const middle = (start+end)/2;
    return `M ${start} ${a.y} C ${middle} ${a.y} ${middle} ${b.y} ${end} ${b.y}`;
  }

  function showConnections(topic) {
    question = topic;
    clearButton.hidden = topic === "all";
    for (const button of buttons) button.setAttribute("aria-pressed", button.dataset.relationQuestion === topic);
    lines.replaceChildren();
    for (const ids of relations[topic] ?? []) {
      const key = ids.join("-");
      const line = svg("a", {class:"case-connection","data-atlas-relation":key,href:comparisonUrl(ids),tabindex:"-1"});
      const d = curve(...ids.map(id => nodes.get(id)));
      line.append(svg("path", {d,class:"case-connection-hit"}), svg("path", {d,class:"case-connection-line"}));
      lines.append(line);
    }
  }

  const relations = Object.fromEntries(Object.entries(pairs).map(([topic, items]) => [
    topic, items.filter(ids => relationFor(ids, topic))
  ]));
  for (const [topic, examples] of Object.entries(relations)) {
    const pairList = section.querySelector(`[data-theme-pairs="${topic}"]`);
    for (const ids of examples) {
      const link = document.createElement("a");
      link.href = comparisonUrl(ids);
      link.textContent = ids.join(" ↔ ");
      link.dataset.atlasRelation = ids.join("-");
      pairList.append(link);
    }
  }
  for (const button of buttons) button.addEventListener("click", () => {
    const topic = button.dataset.relationQuestion;
    showConnections(question === topic ? "all" : topic);
  });
  clearButton.addEventListener("click", () => {
    const active = buttons.find(button => button.dataset.relationQuestion === question);
    showConnections("all");
    active?.focus();
  });
  showConnections("spread");

  return {
    update(selected) {
      const picked = selected.filter(Boolean);
      for (const [id, node] of nodes) {
        if (canCompare(node.row)) node.element.setAttribute("aria-pressed", picked.includes(id));
      }
      status.textContent = picked.length === 2 ? `${picked.join(" and ")} selected. Compare them below.` :
        picked.length ? `${picked[0]} selected. Choose a second case.` : "Select two cases on the atlas to compare them.";
    }
  };
}

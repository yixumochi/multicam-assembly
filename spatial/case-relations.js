function initializeCaseRelations({rows, modes, hasMetres, areaValue, calibration, readableArea, chooseCase, chooseRelation}) {
  const section = document.querySelector(".case-relations");
  const drawing = section.querySelector("svg");
  const buttons = [...section.querySelectorAll("[data-relation-question]")];
  const pairList = section.querySelector(".case-relations-pairs");
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
  let currentRelation = null;

  function svg(tag, attributes = {}, content) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (content !== undefined) element.textContent = content;
    return element;
  }

  const defs = svg("defs");
  for (const [id, size, color] of [["case-grid", 14, "#e0d9c9"], ["case-hatch", 4, "#666456"]]) {
    const pattern = svg("pattern", {id, width:size, height:size, patternUnits:"userSpaceOnUse"});
    pattern.append(svg("path", {d:`M 0 ${size} V 0 H ${size}`, fill:"none", stroke:color, "stroke-width":.48}));
    if (id === "case-hatch") pattern.setAttribute("patternTransform", "rotate(35)");
    defs.append(pattern);
  }
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
      const group = svg("g", {role:"button",tabindex:"0","aria-pressed":"false","data-atlas-case":row.case,
        "aria-label":`${row.case}, ${column.title}. F ${display(row,"object")}, A ${display(row,"activity")}, human ${display(row,"human")}, machine ${display(row,"machine")}`});
      group.append(svg("circle", {cx:x,cy:y,r:Math.max(50,r),class:"case-hit"}));
      group.append(svg("rect", {x:labelX-8,y:y-37,width:111,height:76,class:"case-hit"}));
      group.append(svg("rect", {x:labelX-5,y:y-30,width:103,height:57,class:"case-label-paper"}));
      group.append(svg("text", {x:labelX,y:y-8,class:"case-node-label"}, caseLabel));
      const short = key => area(row,key).toFixed(1);
      if (hasMetres(row)) {
        group.append(svg("text", {x:labelX,y:y+11,class:"case-node-values"}, `A ${short("activity")}   F ${short("object")}`));
        group.append(svg("text", {x:labelX,y:y+25,class:"case-node-values"}, `H ${short("human")}   R ${short("machine")}`));
      }
      group.append(svg("circle", {cx:x,cy:y,r:r || 8,class:"case-node-activity"}));
      if (r) {
        const footprint = radius(area(row,"object"));
        group.append(svg("circle", {cx:x,cy:y,r:footprint,class:"case-node-footprint"}));
        for (const [role, sign] of [["human",-1],["machine",1]]) {
          const extent = radius(area(row,role));
          if (!extent) continue;
          const gap = Math.max(0,r-extent);
          group.append(svg("circle", {cx:x+sign*.75*gap,cy:y-sign*.13*gap,r:extent,class:`case-node-${role}`}));
        }
        group.append(svg("circle", {cx:x,cy:y,r:footprint,fill:"url(#case-hatch)",class:"case-node-hatch"}));
      }
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
    spread:[["V01","V24"], ["V11","V26"]],
    roles:[["V20","V22"], ["V04","V28"]],
    parts:[["V27","V29"]]
  };
  function relationFor(ids) {
    const [a,b] = ids.map(id => byId.get(id));
    if (!a || !b || ![a,b].every(hasMetres)) return null;
    const similar = (key, threshold) => {
      const [x,y] = [area(a,key),area(b,key)];
      return Math.max(x,y) > 0 && Math.abs(x-y) <= threshold*Math.max(x,y);
    };
    let finding;
    if (question === "spread" && similar("object",.20)) {
      const sizes = [area(a,"activity"),area(b,"activity")];
      const ratio = Math.max(...sizes) / Math.min(...sizes);
      if (Number.isFinite(ratio) && ratio >= 1.5) finding = `${a.case} and ${b.case} have similar footprints (${display(a,"object")} and ${display(b,"object")}). Their recorded activity areas are ${display(a,"activity")} and ${display(b,"activity")}, a ${ratio.toFixed(1)}× difference.`;
    }
    if (question === "roles" && similar("object",.20) && similar("activity",.15)) {
      finding = `${a.case} and ${b.case} cover similar total areas (${display(a,"activity")} and ${display(b,"activity")}). Human coverage is ${display(a,"human")} and ${display(b,"human")}, machine coverage is ${display(a,"machine")} and ${display(b,"machine")}, respectively.`;
    }
    if (question === "parts" && similar("part",.15)) {
      finding = `Part coverage is similar (${display(a,"part")} in ${a.case}, ${display(b,"part")} in ${b.case}). Human coverage is ${display(a,"human")} and ${display(b,"human")}, machine coverage is ${display(a,"machine")} and ${display(b,"machine")}, respectively.`;
    }
    return finding ? {ids, finding} : null;
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

  function indicateRelation() {
    const id = currentRelation?.ids.join("-");
    for (const element of section.querySelectorAll("[data-atlas-relation]")) {
      const active = element.dataset.atlasRelation === id;
      element.classList.toggle("is-selected", active);
      if (element instanceof HTMLButtonElement) element.setAttribute("aria-pressed", active);
    }
  }

  function showConnections() {
    lines.replaceChildren();
    pairList.replaceChildren();
    pairList.hidden = question === "all";
    for (const ids of pairs[question] || []) {
      const relation = relationFor(ids);
      if (!relation) continue;
      const key = ids.join("-");
      const pairButton = document.createElement("button");
      pairButton.type = "button";
      pairButton.textContent = ids.join(" ↔ ");
      pairButton.dataset.atlasRelation = key;
      pairButton.addEventListener("click", () => chooseRelation(relation));
      pairList.append(pairButton);
      const line = svg("g", {class:"case-connection","data-atlas-relation":key});
      const d = curve(...ids.map(id => nodes.get(id)));
      line.append(svg("path", {d,class:"case-connection-hit"}), svg("path", {d,class:"case-connection-line"}));
      line.addEventListener("click", () => chooseRelation(relation));
      lines.append(line);
    }
    if (!pairList.hidden && !pairList.children.length) pairList.textContent = "No examples match this question.";
    indicateRelation();
  }

  for (const button of buttons) button.addEventListener("click", () => {
    question = button.dataset.relationQuestion;
    for (const choice of buttons) choice.setAttribute("aria-pressed", choice === button);
    showConnections();
  });

  return {
    update(selected, relation) {
      const picked = selected.filter(Boolean);
      currentRelation = relation;
      for (const [id, node] of nodes) node.element.setAttribute("aria-pressed", picked.includes(id));
      indicateRelation();
      status.textContent = picked.length === 2 ? `${picked.join(" and ")} selected. Compare them below.` :
        picked.length ? `${picked[0]} selected. Choose a second case.` : "Select a case to start a comparison.";
    }
  };
}

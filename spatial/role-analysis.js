function initializeSpatialRoles({rows, modes, median, caseUrl, showPlan, frameUrl}) {
  const root = document.getElementById("roles");
  const chart = root.querySelector("#roles-chart");
  const denominator = root.querySelector("#roles-denominator");
  const basis = root.querySelector("#roles-basis");
  const caseSelect = root.querySelector("#roles-case");
  const layerSelect = root.querySelector("#roles-layer");
  const roles = {human:"Human", machine:"Machine", part:"Parts"};
  const keys = Object.keys(roles);
  const byId = new Map(rows.map(row => [row.case, row]));
  const examples = {
    "human-led": {
      ids:["V01"], role:"part",
      message:"Parts cover a median 89% of the activity area. Follow a component’s route to assess where delivery, turning and temporary storage fit."
    },
    "human-robot": {
      ids:["V27","V21"], role:"human",
      message:"Human coverage is 58% in V27. Machine coverage is 63% in V21. Compare the plans to investigate where people approach or take over during positioning and support."
    },
    "robotic-assembly": {
      ids:["V26","V28"], role:"machine",
      message:"Machine coverage exceeds part coverage in V26 (61% vs 45%). Parts cover more in V28 (90% vs 43%). Look at machine placement in V26 and the supply route in V28."
    }
  };
  const preferredLayers = {V01:"part", V27:"human", V21:"machine", V26:"machine", V28:"part"};
  const questions = {
    human:"Check where people approach the work and whether access crosses machine or part routes.",
    machine:"Check where the machine moves relative to the object and whether the layout can accommodate that motion.",
    part:"Check where the part enters, turns or waits relative to the assembled object."
  };

  const node = (tag, css, label) => {
    const element = document.createElement(tag);
    if (css) element.className = css;
    if (label !== undefined) element.textContent = label;
    return element;
  };
  const fraction = (row, role) => {
    const field = denominator.value === "activity" ? "activity_area_m2" : "object_area_m2";
    return row[role + "_area_m2"] / row[field];
  };
  const printed = value => denominator.value === "activity" ? (value * 100).toFixed(1) + "%" : value.toFixed(2) + "×";
  const pos = value => denominator.value === "activity"
    ? 100 * value
    : 100 * Math.log1p(value) / Math.log1p(40);
  const updatePlan = () => {
    const row = byId.get(caseSelect.value);
    const role = layerSelect.value;
    const {drawing, track} = showPlan(row, role, longestVisibleTrack);
    for (const button of chart.querySelectorAll("[data-role-case]")) {
      button.setAttribute("aria-pressed", String(button.dataset.roleCase === row.case));
    }
    const current = root.querySelector("#roles-detail");
    sheetLink.href = caseUrl(row);
    current.textContent = row.case + " · " + keys.map(key => roles[key] + " " + printed(fraction(row,key))).join(" · ") +
      " · Total A/F " + row.ratio_activity_over_object.toFixed(2) + "×";
    root.querySelector("#roles-plan-drawing").replaceChildren(drawing);
    const details = root.querySelector("#roles-plan-note");
    details.replaceChildren();
    if (track) {
      details.append(document.createTextNode("Highlighted " + roles[role].toLowerCase() + " track " + track.id + " · "));
      for (const [index, endpoint] of [track.start, track.end].entries()) {
        const href = frameUrl(endpoint?.src);
        const label = (index + 1) + " " + (index ? "End" : "Start") +
          (Number.isFinite(endpoint?.time) ? " (" + endpoint.time.toFixed(1) + " s)" : "");
        if (index) details.append(document.createTextNode(" → "));
        const cue = node(href ? "a" : "span", "", label);
        if (href) cue.href = href;
        details.append(cue);
      }
      details.append(document.createTextNode(". Dashed outline shows object bounds. " + questions[role]));
    } else {
      details.textContent = "No saved " + roles[role].toLowerCase() + " track with visible start and end points for this case.";
    }
  };

  function longestVisibleTrack(actions, [left, top, width, height]) {
    const visible = ([x, y]) => x >= left && x <= left + width && y >= top && y <= top + height;
    let track;
    let longest = 0;
    for (const action of actions) {
      if (!action.line || action.line.length < 2) continue;
      const first = action.line[0];
      const last = action.line.at(-1);
      if (!visible(first) || !visible(last)) continue;
      const distance = Math.hypot(last[0] - first[0], last[1] - first[1]);
      if (distance > longest) {
        longest = distance;
        track = action;
      }
    }
    return track;
  }

  function choose(id, role) {
    caseSelect.value = id;
    layerSelect.value = preferredLayers[id] || role || [...keys].sort((left,right) => fraction(byId.get(id),right) - fraction(byId.get(id),left))[0];
    updatePlan();
    root.querySelector("#role-plan-title").focus();
  }

  function comparisonRow(label, values, total, summary, contextualRole) {
    const row = node("div", "role-row" + (summary ? " role-median" : ""));
    const name = node(summary ? "span" : "button", "role-case-label", label);
    if (!summary) {
      name.type = "button";
      name.dataset.roleCase = label;
      name.addEventListener("click", () => choose(label, contextualRole));
    }
    row.append(name);
    for (const [index, role] of keys.entries()) {
      const cell = node("div", "role-cell role-" + role);
      const axis = node("span", "role-axis");
      axis.setAttribute("aria-hidden", "true");
      const mark = node("i", "role-mark");
      mark.style.setProperty("--position", pos(values[index]) + "%");
      axis.append(mark);
      const value = node("span", "role-number", printed(values[index]));
      value.setAttribute("aria-label", roles[role] + " " + printed(values[index]));
      cell.append(axis, value);
      row.append(cell);
    }
    row.append(node("span", "role-total", total.toFixed(2) + "×"));
    return row;
  }

  function renderChart() {
    basis.textContent = denominator.value === "activity"
      ? "Shared 0–100% scale. Diamonds mark group medians. Role areas can overlap."
      : "Shared scale from 0 to 40×, using log(1 + ratio) to keep small values visible. Diamonds mark group medians.";
    const header = node("div", "role-row role-header");
    header.append(node("span", "", "Case"));
    for (const role of keys) header.append(node("span", "role-key role-" + role, roles[role]));
    header.append(node("span", "role-total", "Total A/F"));
    chart.replaceChildren(header);
    for (const mode of modes) {
      const group = rows.filter(row => row.mode === mode.mode);
      const example = examples[mode.mode];
      const section = node("section", "role-mode");
      section.append(node("h3", "", mode.title + " · " + group.length + " cases"));
      const interpretation = node("div", "role-interpretation");
      interpretation.append(node("p", "", example.message));
      for (const id of example.ids) {
        const button = node("button", "role-example", "View " + id + " plan");
        button.type = "button";
        button.addEventListener("click", () => choose(id, example.role));
        interpretation.append(button);
      }
      section.append(interpretation);
      const medians = keys.map(role => median(group.map(row => fraction(row,role))));
      section.append(comparisonRow("Median", medians, median(group.map(row => row.ratio_activity_over_object)), true, example.role));
      for (const row of group) section.append(comparisonRow(row.case, keys.map(role => fraction(row,role)), row.ratio_activity_over_object, false, example.role));
      chart.append(section);
    }
    updatePlan();
  }

  for (const row of rows) caseSelect.add(new Option(row.case + " · " + modes.find(mode => mode.mode === row.mode).title, row.case));
  caseSelect.value = "V27";
  layerSelect.value = "human";
  caseSelect.addEventListener("change", updatePlan);
  layerSelect.addEventListener("change", updatePlan);
  denominator.addEventListener("change", renderChart);
  root.querySelector("#roles-plan-link").addEventListener("click", event => {
    event.preventDefault();
    root.querySelector("#role-plan-title").focus();
  });
  const sheetLink = node("a","role-sheet-link","Open source case sheet");
  root.querySelector("#role-plan").append(sheetLink);
  renderChart();
  root.querySelector("#roles-status").hidden = true;
  root.querySelector("#roles-content").hidden = false;
}

(() => {
  const atlas = document.getElementById("atlas");
  const overview = document.getElementById("overview");
  const casePage = new URL("../index.html", location.href);
  const exceptions = {
    V23: "Footprint from the saved truss",
    V24: "Coverage from the saved local registration",
    V27: "Footprint from rod projection",
    V28: "Coverage from the saved shelter plan"
  };
  const sensitivityCases = new Set(["V07", "V21", "V27"]);
  const metric = row => row.unit === "mm_to_m";
  const calibration = row => metric(row) ? undefined : areaCalibration[row.case];
  const hasMetres = row => metric(row) || Boolean(calibration(row));
  const unit = row => hasMetres(row) ? "m²" : "model units²";
  const scale = reference => reference.referenceMetres / reference.bounds[reference.axis];
  const areaValue = (row, field) => {
    const reference = calibration(row);
    return reference ? row[field] * scale(reference) ** 2 : row[field];
  };
  const format = value => value.toFixed(3);
  const multiplier = row => format(row.ratio_activity_over_object) + "×";
  const caseUrl = row => casePage.href + "#" + row.mode + "/" + row.case;
  const svgNamespace = "http://www.w3.org/2000/svg";
  const coordinates = points => points.map(point => point.join(",")).join(" ");

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function svgElement(tag, attributes) {
    const node = document.createElementNS(svgNamespace, tag);
    for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
    return node;
  }

  function axis(maximum, label) {
    const node = element("div", "atlas-axis");
    for (let tick = 0; tick <= 4; tick++) {
      node.append(element("span", "", (maximum * tick / 4).toLocaleString("en") + (tick === 4 ? " " + label : "")));
    }
    return node;
  }

  function bars(row, maximum) {
    const node = element("div", "atlas-bars");
    const reference = calibration(row);
    for (const [key, label, field] of [
      ["footprint", "F", "object_area_m2"],
      ["activity", "A", "activity_area_m2"]
    ]) {
      const value = areaValue(row, field);
      const line = element("div", "atlas-bar-line");
      const track = element("span", "atlas-track");
      const fill = element("span", "atlas-fill " + key);
      fill.style.width = 100 * value / maximum + "%";
      track.append(fill);
      const amount = reference ? "≈" + value.toFixed(reference.digits) : format(value);
      line.append(element("b", "atlas-bar-label", label), track, element("span", "atlas-value", amount + " " + unit(row)));
      node.append(line);
    }
    return node;
  }

  function nativeMetresPerPixel(row, data, granted) {
    if (!metric(row) || !granted.has(row.case) || !data.object_range) return null;
    const [left, top, right, bottom] = data.object_range;
    const horizontal = row.object_aabb_m[0] / Math.abs(right - left);
    const vertical = row.object_aabb_m[1] / Math.abs(bottom - top);
    if (!Number.isFinite(horizontal) || !Number.isFinite(vertical) || horizontal <= 0 || vertical <= 0) return null;
    return Math.abs(horizontal / vertical - 1) <= 0.01 ? (horizontal + vertical) / 2 : null;
  }

  function getPlan(source, row, granted) {
    const article = source.querySelector("#" + row.case);
    const plan = article.querySelector('.plan[data-layer="all"] svg');
    const data = JSON.parse(article.querySelector('script[type="application/json"]').textContent);
    const viewBox = plan.getAttribute("viewBox").split(/\s+/).map(Number);
    return {plan, data, viewBox, metres: nativeMetresPerPixel(row, data, granted)};
  }

  function renderPlan(row, {plan, data, viewBox, metres}, shared, layers) {
    const panel = element("article", "atlas-card");
    const link = element("a", "", row.case + " case sheet");
    link.href = caseUrl(row);
    const title = element("h4");
    title.append(link);
    const [left, top, width, height] = viewBox;
    const canvas = svgElement("svg", {
      viewBox: shared ? `0 0 ${shared.width} ${shared.height}` : viewBox.join(" "),
      role: "img", "aria-label": row.case + " original top drawing and selected activity tracks"
    });
    const geometry = svgElement("g", {});
    if (shared) {
      const offsetX = (shared.width - width * metres) / 2;
      const offsetY = (shared.height - height * metres) / 2;
      geometry.setAttribute("transform", `translate(${offsetX} ${offsetY}) scale(${metres}) translate(${-left} ${-top})`);
    }
    const backdrop = plan.querySelector("image").cloneNode(true);
    backdrop.setAttribute("href", new URL(backdrop.getAttribute("href"), casePage).href);
    backdrop.setAttribute("opacity", "0.55");
    geometry.append(backdrop);
    for (const action of data.actions) {
      if (!layers.has(action.role) || !action.poly?.length) continue;
      geometry.append(svgElement("polygon", {
        points:coordinates(action.poly), fill:action.color, "fill-opacity":0.18, stroke:action.color
      }));
      if (action.line?.length > 1) geometry.append(svgElement("polyline", {
        points:coordinates(action.line), fill:"none", stroke:action.color
      }));
    }
    if (data.object_range) {
      const [minX, minY, maxX, maxY] = data.object_range;
      geometry.append(svgElement("rect", {
        x:Math.min(minX,maxX), y:Math.min(minY,maxY), width:Math.abs(maxX-minX), height:Math.abs(maxY-minY),
        fill:"none", stroke:"#193f4d", "stroke-dasharray":"5 3"
      }));
    }
    canvas.append(geometry);
    if (shared) {
      const start = shared.width * 0.04;
      const baseline = shared.height * 0.94;
      const length = shared.width >= 15 ? 5 : 1;
      canvas.append(svgElement("line", {x1:start, x2:start+length, y1:baseline, y2:baseline, stroke:"#193f4d"}));
      const label = svgElement("text", {x:start, y:baseline-shared.height*.024, "font-size":shared.width*.035, fill:"#193f4d"});
      label.textContent = length + " m";
      canvas.append(label);
    }
    panel.append(title, canvas, element("p", "note", shared ? "Shared metre scale" : "Fit to saved plan · " + (metric(row) ? "metric case" : "model units")));
    return panel;
  }

  function median(values) {
    const ordered = [...values].sort((left, right) => left - right);
    const middle = Math.floor(ordered.length / 2);
    return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
  }

  function start(source, {rows, modes}, registered) {
    const metricLimit = Math.ceil(Math.max(...rows.filter(hasMetres).flatMap(row => [
      areaValue(row, "activity_area_m2"), areaValue(row, "object_area_m2")
    ])) / 20) * 20;
    const modelLimit = row => Math.ceil(Math.max(row.activity_area_m2, row.object_area_m2) / 10) * 10;
    const first = atlas.querySelector("#compare-first");
    const second = atlas.querySelector("#compare-second");
    const areaChart = overview.querySelector("#atlas-areas");
    const byId = new Map(rows.map(row => [row.case, row]));
    const picked = [first, second];
    for (const select of picked) {
      for (const row of rows) select.add(new Option(row.case, row.case));
    }
    first.value = "V01";
    second.value = "V30";

    function areaRow(row, maximum) {
      const wrapper = element("div", "atlas-case-row");
      const choose = element("button", "atlas-case-button", row.case);
      choose.type = "button";
      choose.dataset.case = row.case;
      choose.setAttribute("aria-label", "Compare " + row.case + " in Spatial atlas");
      choose.addEventListener("click", () => {
        if (first.value !== row.case && second.value !== row.case) {
          first.value = second.value;
          second.value = row.case;
          renderComparison();
        }
        const focusComparison = () => atlas.querySelector("#compare-title").focus();
        if (location.hash === "#atlas") focusComparison();
        else {
          window.addEventListener("hashchange", focusComparison, {once:true});
          location.hash = "atlas";
        }
      });
      const sourceLink = element("a", "atlas-source", "Case sheet ↗");
      sourceLink.href = caseUrl(row);
      const identity = element("div", "atlas-identity");
      identity.append(choose, sourceLink);
      const note = calibration(row)?.label || exceptions[row.case];
      if (note) identity.append(element("small", "", note));
      wrapper.append(identity, bars(row, maximum), element("b", "atlas-ratio", multiplier(row)));
      return wrapper;
    }

    function renderAreas() {
      const header = element("div", "atlas-case-row atlas-table-header");
      header.append(element("span", "", "Case"), axis(metricLimit, "m²"), element("span", "", "A/F"));
      areaChart.append(header);
      for (const mode of modes) {
        const group = element("section", "atlas-area-group");
        group.append(element("h3", "", mode.title));
        const ordered = rows.filter(row => row.mode === mode.mode && hasMetres(row))
          .sort((left, right) => areaValue(right, "activity_area_m2") - areaValue(left, "activity_area_m2"));
        for (const row of ordered) {
          group.append(areaRow(row, metricLimit));
          if (calibration(row)) group.append(calibrationDetails(row));
        }
        areaChart.append(group);
      }
      const unscaled = rows.filter(row => !hasMetres(row));
      if (unscaled.length) {
        const models = element("section", "atlas-area-group atlas-models");
        models.append(element("h3", "", "Model-unit cases"));
        for (const row of unscaled) {
          const maximum = modelLimit(row);
          const caseRow = areaRow(row, maximum);
          caseRow.querySelector(".atlas-bars").prepend(axis(maximum, ""));
          models.append(caseRow);
        }
        areaChart.append(models);
      }
    }

    function calibrationDetails(row) {
      const reference = calibration(row);
      const factor = scale(reference);
      const dimensions = reference.bounds.map(value => (value * factor).toFixed(reference.digits || 1));
      const detail = element("details", "atlas-calibration");
      const sourceLink = element("a", "", reference.source);
      sourceLink.href = reference.url;
      detail.append(element("summary", "", row.case + " scale and source"),
        element("p", "", `Scaled model bounds (X × Y × Z) ≈ ${dimensions.join(" × ")} m. The conversion uses ${factor.toFixed(4)} m per model unit. Original F ${format(row.object_area_m2)} and A ${format(row.activity_area_m2)} model units² are multiplied by the square of that scale.`),
        element("p", "", `Rhino model ${reference.modelFile} supplies the reconstructed geometry used for these estimates.`), sourceLink);
      return detail;
    }

    function renderComparison() {
      const pair = picked.map(select => byId.get(select.value));
      for (const select of picked) {
        const other = select === first ? second : first;
        for (const option of select.options) option.disabled = option.value === other.value;
      }
      for (const button of areaChart.querySelectorAll(".atlas-case-button")) {
        button.setAttribute("aria-pressed", String(pair.some(row => row.case === button.dataset.case)));
      }
      const compareBars = atlas.querySelector("#compare-bars");
      const plans = atlas.querySelector("#compare-plans");
      compareBars.replaceChildren();
      plans.replaceChildren();
      const [larger, smaller] = [...pair].sort((left, right) => right.activity_area_m2 - left.activity_area_m2);
      const [higher, lower] = [...pair].sort((left, right) => right.ratio_activity_over_object - left.ratio_activity_over_object);
      const findings = atlas.querySelector("#compare-findings");
      const areaFinding = pair.every(metric) ? (larger.activity_area_m2 === smaller.activity_area_m2
        ? "Both cases have the same activity area."
        : `${larger.case} covers more area during assembly (${format(larger.activity_area_m2)} vs ${format(smaller.activity_area_m2)} m²).`)
        : "The selected comparison includes a literature-scaled area estimate (≈).";
      const ratioFinding = higher.ratio_activity_over_object === lower.ratio_activity_over_object
        ? "Both cases have the same A/F."
        : `${higher.case} has the higher A/F (${multiplier(higher)} vs ${multiplier(lower)}).`;
      const denominator = pair.every(metric) && higher.case !== larger.case
        && larger.activity_area_m2 !== smaller.activity_area_m2
        && higher.ratio_activity_over_object > lower.ratio_activity_over_object
        ? ` Its object footprint is smaller (${format(higher.object_area_m2)} vs ${format(lower.object_area_m2)} m²).` : "";
      findings.textContent = areaFinding + " " + ratioFinding + denominator;
      const planData = pair.map(row => getPlan(source, row, registered));
      const common = atlas.querySelector("#atlas-common");
      const canShare = planData.every(plan => plan.metres);
      common.disabled = !canShare;
      const shared = canShare && common.checked ? {
        width:Math.max(...planData.map(plan => plan.viewBox[2]*plan.metres)),
        height:Math.max(...planData.map(plan => plan.viewBox[3]*plan.metres))
      } : null;
      const layers = new Set([...atlas.querySelectorAll(".atlas-layers input[value]:checked")].map(input => input.value));
      atlas.querySelector("#atlas-plan-note").textContent = "The authored footprint is shown in the original top drawing. The dashed box marks its saved bounds. " +
        (canShare ? "Shared scale uses the saved metric registration. " : "These cases are displayed at their own plan scales. ") +
        "Area beyond the object requires the intersection of activity coverage with the actual footprint.";
      pair.forEach((row, index) => {
        const card = element("article", "atlas-card");
        const maximum = hasMetres(row) ? metricLimit : modelLimit(row);
        card.append(element("h4", "", row.case + " · A/F " + multiplier(row)), bars(row, maximum), axis(maximum, unit(row)));
        compareBars.append(card);
        plans.append(renderPlan(row, planData[index], shared, layers));
      });
    }

    function groupChart(active, key, title, maximum, suffix) {
      const card = element("div", "atlas-card atlas-distribution");
      card.append(element("h4", "", title), axis(maximum, suffix));
      for (const mode of modes) {
        const data = active.filter(row => row.mode === mode.mode);
        const centre = median(data.map(row => row[key]));
        const group = element("div", "atlas-distribution-group");
        group.append(element("h5", "", `${mode.title} · n=${data.length} · median ${format(centre)}${suffix === "×" ? "" : " "}${suffix}`));
        const plot = element("div", "atlas-dot-plot");
        const marker = element("span", "atlas-median");
        marker.style.left = 100 * centre / maximum + "%";
        plot.append(marker);
        const laneEnds = [];
        const ordered = [...data].sort((left, right) => left[key] - right[key]);
        for (const row of ordered) {
          const position = 100 * row[key] / maximum;
          const cleared = laneEnds.findIndex(end => position - end > 13);
          const lane = cleared === -1 ? laneEnds.length : cleared;
          laneEnds[lane] = position;
          const point = element("a", "atlas-point", row.case);
          point.href = caseUrl(row);
          point.title = row.case + " · " + format(row[key]) + " " + suffix;
          point.style.left = position + "%";
          point.style.top = (18 + lane*24) + "px";
          plot.append(point);
        }
        plot.style.height = (27 + laneEnds.length*24) + "px";
        group.append(plot);
        card.append(group);
      }
      return card;
    }

    function renderGroups() {
      const checked = atlas.querySelector("#atlas-sensitive").checked;
      const active = rows.filter(row => !checked || !sensitivityCases.has(row.case));
      const ratioLimit = Math.ceil(Math.max(...rows.map(row => row.ratio_activity_over_object)) / 10) * 10;
      const renderer = atlas.querySelector("#atlas-groups");
      renderer.replaceChildren(groupChart(active.filter(metric), "activity_area_m2", "Activity area (A)", metricLimit, "m²"),
        groupChart(active, "ratio_activity_over_object", "Activity / footprint (A/F)", ratioLimit, "×"));
      const base = median(rows.filter(row => row.mode === "human-led").map(row => row.ratio_activity_over_object));
      const current = median(active.filter(row => row.mode === "human-led").map(row => row.ratio_activity_over_object));
      atlas.querySelector("#atlas-group-note").textContent = checked
        ? `Human-led median A/F moves from ${base.toFixed(2)}× to ${current.toFixed(2)}× with the selected exclusions.`
        : "The area chart uses the 13 cases with existing metric scales. V07 and V21 are shown separately with literature-scaled estimates. The ratio chart includes all 15.";
    }

    renderAreas();
    renderComparison();
    renderGroups();
    for (const select of picked) select.addEventListener("change", renderComparison);
    atlas.querySelector(".atlas-layers").addEventListener("change", renderComparison);
    atlas.querySelector("#atlas-sensitive").addEventListener("change", renderGroups);
    atlas.querySelector("#atlas-status").hidden = true;
    atlas.querySelector("#atlas-content").hidden = false;
    overview.querySelector("#overview-status").hidden = true;
    overview.querySelector("#overview-content").hidden = false;
  }

  async function load() {
    const [response, registration] = await Promise.all([
      fetch(casePage),
      fetch("case_area_comparison.csv").catch(() => null)
    ]);
    if (!response.ok) throw new Error("Case page: " + response.status);
    const source = document.createElement("template");
    source.innerHTML = await response.text();
    const areaData = JSON.parse(source.content.querySelector("#ma-data").textContent);
    const registered = new Set();
    if (registration?.ok) {
      for (const line of (await registration.text()).split(/\r?\n/)) {
        const caseId = line.match(/^"?(V\d+)"?,/)?.[1];
        if (caseId && line.includes('"registered metric union"')) registered.add(caseId);
      }
    }
    start(source.content, areaData, registered);
  }

  load().catch(error => {
    console.error(error);
    for (const status of [atlas.querySelector("#atlas-status"), overview.querySelector("#overview-status")]) {
      status.textContent = "Could not load the case measurements. Reload the page to try again.";
    }
  });
})();

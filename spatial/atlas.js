(() => {
  const atlas = document.getElementById("atlas");
  const comparisonPage = atlas.hasAttribute("data-compare-page");
  const casePage = new URL("../index.html", location.href);
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
  const readableArea = (row, field) => {
    const reference = calibration(row);
    const value = areaValue(row, field);
    return (reference ? "≈" + value.toFixed(reference.digits) : format(value)) + " " + unit(row);
  };
  const multiplier = row => format(row.ratio_activity_over_object) + "×";
  const shareOfActivity = (row, field) => row.activity_area_m2 > 0 ? 100 * row[field] / row.activity_area_m2 : NaN;
  const readableShare = value => Number.isFinite(value) ? value.toFixed(1) + "%" : "Unavailable";
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

  function nativeMetresPerPixel(row, data, granted) {
    if (!metric(row) || !granted.has(row.case) || !data.object_range) return null;
    const [left, top, right, bottom] = data.object_range;
    const horizontal = row.object_aabb_m[0] / Math.abs(right - left);
    const vertical = row.object_aabb_m[1] / Math.abs(bottom - top);
    if (!Number.isFinite(horizontal) || !Number.isFinite(vertical) || horizontal <= 0 || vertical <= 0) return null;
    return Math.abs(horizontal / vertical - 1) <= 0.01 ? (horizontal + vertical) / 2 : null;
  }

  function getPlan(source, row, granted, outlines) {
    const article = source.querySelector("#" + row.case);
    const plan = article.querySelector('.plan[data-layer="all"] svg');
    const data = JSON.parse(article.querySelector('script[type="application/json"]').textContent);
    const viewBox = plan.getAttribute("viewBox").split(/\s+/).map(Number);
    const iso = article.querySelector('img[src*="_model_iso."]')?.getAttribute("src");
    const trace = outlines[row.case];
    const outline = trace?.plan === data.plan?.split("?")[0] ? trace.points : null;
    return {plan, data, viewBox, iso, outline, metres: nativeMetresPerPixel(row, data, granted)};
  }

  function areaPlanBox({data, viewBox, outline}) {
    if (!data.object_range) return viewBox;
    const [x1, y1, x2, y2] = data.object_range;
    const points = [[x1, y1], [x2, y2], ...(outline ?? []), ...data.actions.flatMap(action => action.poly ?? [])];
    const xs = points.map(([x]) => x);
    const ys = points.map(([, y]) => y);
    const left = Math.min(...xs), top = Math.min(...ys);
    const width = Math.max(...xs) - left, height = Math.max(...ys) - top;
    const margin = Math.max(width, height) * .075;
    return margin > 0 ? [left - margin, top - margin, width + margin * 2, height + margin * 2] : viewBox;
  }

  function filledCoverage(geometry, actions, layers, caseId, mergeRoles) {
    const byRole = new Map();
    for (const action of actions) {
      if (!layers.has(action.role) || (action.poly?.length ?? 0) < 3) continue;
      const signedArea = action.poly.reduce((sum, [x,y], index, points) => {
        const [nextX,nextY] = points[(index+1)%points.length];
        return sum + x*nextY - nextX*y;
      },0);
      if (!Number.isFinite(signedArea) || signedArea === 0) continue;
      const ring = signedArea > 0 ? action.poly : [...action.poly].reverse();
      const role = mergeRoles ? "activity" : action.role;
      byRole.set(role, (byRole.get(role) || "") + `M ${coordinates(ring)} Z `);
    }
    for (const [role, d] of byRole) {
      geometry.append(svgElement("path", {d,class:"atlas-coverage-fill","data-coverage-layer":role,"fill-rule":"nonzero"}));
    }
    if (byRole.has("human") && byRole.has("machine")) {
      const id = `atlas-human-clip-${caseId}`;
      const clip = svgElement("clipPath", {id,clipPathUnits:"userSpaceOnUse"});
      clip.append(svgElement("path", {d:byRole.get("human"),"clip-rule":"nonzero"}));
      geometry.append(clip,svgElement("path", {d:byRole.get("machine"),class:"atlas-coverage-fill",
        "data-coverage-layer":"overlap","clip-path":`url(#${id})`,"fill-rule":"nonzero"}));
    }
  }

  const planLayers = {
    footprint: [],
    activity: ["human","machine","part"],
    parts: ["part"],
    operators: ["human","machine"]
  };

  function renderPlan(row, {plan, data, viewBox, metres, outline}, shared, mode, label) {
    const [left, top, width, height] = viewBox;
    const canvas = svgElement("svg", {
      viewBox: shared ? `0 0 ${shared.width} ${shared.height}` : viewBox.join(" "),
      class:"atlas-coverage-canvas", role:"img", "aria-label":row.case + " Top View · " + label
    });
    const geometry = svgElement("g", {});
    if (shared) {
      const offsetX = (shared.width - width * metres) / 2;
      const offsetY = (shared.height - height * metres) / 2;
      geometry.setAttribute("transform", `translate(${offsetX} ${offsetY}) scale(${metres}) translate(${-left} ${-top})`);
    }
    const backdrop = plan.querySelector("image").cloneNode(true);
    backdrop.setAttribute("href", new URL(backdrop.getAttribute("href"), casePage).href);
    backdrop.setAttribute("opacity", mode === "footprint" ? "0.9" : outline ? "0.5" : "0.7");
    geometry.classList.add("atlas-coverage-plan");
    backdrop.classList.add("atlas-coverage-drawing");
    filledCoverage(geometry, data.actions, new Set(planLayers[mode]), row.case, mode === "activity");
    geometry.append(backdrop);
    if (outline) geometry.append(svgElement("path", {
      d:`M ${coordinates(outline)} Z`, class:"atlas-object-outline"
    }));
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
    return canvas;
  }

  function caseLink(row) {
    const link = element("a", "", row.case);
    link.setAttribute("aria-label", row.case + " case sheet");
    link.href = caseUrl(row);
    return link;
  }

  function modelNumber(value, unit, approximate = false) {
    return Number.isFinite(value)
      ? (approximate ? "≈" : "") + value.toLocaleString("en", {maximumFractionDigits:unit === "m³" ? 3 : 2}) + " " + unit
      : "Unverified";
  }

  function modelDimensions(metrics) {
    const dimensions = metrics?.dimensions;
    if (!dimensions) return "Unverified";
    return "≈" + dimensions.map(value => value.toFixed(2)).join(" × ") + " m" +
      (metrics.dimensionPose ? ` (${metrics.dimensionPose})` : "");
  }

  function metricCard(row, metrics, plan) {
    const card = element("div", "compare-model-card");
    if (plan.iso) {
      const figure = element("figure", "pair-study-iso");
      const image = element("img");
      image.src = new URL(plan.iso, casePage).href;
      image.alt = row.case + " isometric view from Fifteen assembly cases";
      image.loading = "lazy";
      const pose = metrics?.dimensionPose ? ` (${metrics.dimensionPose})` : "";
      const height = metrics?.dimensions ? " · Height " + modelNumber(metrics.dimensions[2], "m", true) + pose : "";
      figure.append(image, element("figcaption", "", "ISO" + height));
      card.append(figure);
    }
    const facts = element("dl", "pair-study-facts");
    facts.append(element("dt", "", "Dimensions (X × Y × Z)"), element("dd", "", modelDimensions(metrics)));
    card.append(facts);
    if (metrics?.members) {
      const details = element("details", "note pair-study-model-source");
      details.append(element("summary", "", "Model scope"), element("p", "", metrics.scope), element("p", "", metrics.file));
      card.append(details);
    } else if (metrics) {
      card.append(element("p", "note", metrics.scope));
    }
    return card;
  }

  function pieGraphic(shares) {
    const pie = svgElement("svg", {viewBox:"0 0 80 80",class:"atlas-pie-svg","aria-hidden":"true"});
    pie.append(svgElement("circle", {cx:40,cy:40,r:36,class:"atlas-pie-base"}));
    const endpoint = fraction => {
      const angle = 2*Math.PI*fraction/100;
      return `${40+36*Math.sin(angle)} ${40-36*Math.cos(angle)}`;
    };
    let start = 0;
    for (const [share, color] of shares) {
      if (share === 100) {
        pie.append(svgElement("circle", {cx:40,cy:40,r:36,class:color}));
      } else if (share > 0 && share < 100) {
        pie.append(svgElement("path", {class:color,
          d:`M 40 40 L ${endpoint(start)} A 36 36 0 ${share > 50 ? 1 : 0} 1 ${endpoint(start+share)} Z`}));
      }
      start += share;
    }
    return pie;
  }

  const studyRows = [
    {mode:"footprint", name:"Finished footprint", keys:["object"], tolerance:.20},
    {mode:"activity", name:"Total activity area", keys:["activity"], tolerance:.15},
    {mode:"parts", name:"Parts & access", keys:["part"], tolerance:.15},
    {mode:"operators", name:"Human & machine", keys:["human","machine"]}
  ];

  const findingsByPair = {
    "V01-V24":"The finished footprints are close. V01’s recorded assembly area is 4.3× V24’s, and its part tracks cover 5.5× as much ground. The finished V24 model has 338 members versus 58 in V01.",
    "V11-V26":"The footprints are close, while V11 covers more ground during assembly. Its part tracks account for most of the recorded work area. V26’s largest recorded layer is machine movement.",
    "V20-V22":"The total activity areas are close. The plans show different uses of that space. V20 records human movement alongside the shell and V22 records machine movement around the pod.",
    "V04-V28":"The total activity areas are close. Parts cover a larger share of that area in V28, while the human and machine layers are both present in V04. The layers show where each type of movement concentrates.",
    "V27-V29":"The part movement areas are close. V27 records more human coverage and V29 records more machine coverage. The operator plans show where each case uses the space around its parts."
  };

  function compareUrl(cases) {
    const url = new URL("compare.html", location.href);
    cases.forEach((id, index) => { if (id) url.searchParams.set(index ? "second" : "first", id); });
    return url;
  }

  function readAtlas({rows, modes}) {
    const ids = new Set(rows.map(row => row.case));
    const compareTab = document.getElementById("compare-tab-link");
    let selected = [];
    const relations = initializeCaseRelations({
      rows, modes, hasMetres, areaValue, calibration, readableArea,
      comparisonUrl: ids => compareUrl(ids).href,
      chooseCase(id) {
        if (selected.includes(id)) {
          selected = [];
        } else if (selected.length) {
          location.assign(compareUrl([selected[0], id]).href);
          return;
        } else {
          selected = [id];
        }
        updateSelection();
      }
    });
    function updateSelection() {
      relations.update(selected);
      compareTab.href = compareUrl(selected).href;
    }
    function openLinkedCase() {
      const id = location.hash.slice(1);
      selected = ids.has(id) ? [id] : [];
      updateSelection();
    }
    openLinkedCase();
    window.addEventListener("hashchange", openLinkedCase);
  }

  function rowLayout(label, left, middle, right) {
    const row = element("div", "compare-row");
    label.classList.add("compare-row-label");
    left.classList.add("compare-left");
    middle.classList.add("compare-middle");
    right.classList.add("compare-right");
    row.append(label, left, middle, right);
    return row;
  }

  function comparisonLabel(study, pair) {
    const header = element("div", "");
    header.append(element("h3", "", study.name));
    if (study.tolerance && pair.every(hasMetres)) {
      const field = study.keys[0] + "_area_m2";
      const values = pair.map(row => areaValue(row, field));
      const similar = Math.abs(values[0] - values[1]) <= study.tolerance * Math.max(...values);
      const badge = element("span", "compare-badge", similar ? "Similar" : "Different");
      badge.dataset.similar = String(similar);
      header.append(badge);
    }
    return header;
  }

  function bindHighlights(controls, plan) {
    let locked = "";
    for (const [button, layer] of controls) {
      const highlight = () => { plan.dataset.emphasis = layer; };
      const restore = () => { plan.dataset.emphasis = locked; };
      button.addEventListener("pointerenter", highlight);
      button.addEventListener("pointerleave", restore);
      button.addEventListener("focus", highlight);
      button.addEventListener("blur", restore);
      button.addEventListener("click", () => {
        locked = locked === layer ? "" : layer;
        for (const [peer, key] of controls) peer.setAttribute("aria-pressed", String(key === locked));
        restore();
      });
    }
  }

  function chartButton(row, key) {
    const button = element("button", "compare-chart-button");
    button.type = "button";
    button.dataset.coverageRole = key;
    button.setAttribute("aria-pressed", "false");
    button.setAttribute("aria-label", row.case + " " + {
      object:"finished footprint", activity:"total activity and footprint",
      part:"part movement", human:"human coverage", machine:"machine coverage"
    }[key]);
    return button;
  }

  function measureTrack(fraction) {
    const track = element("span", "compare-measure-track");
    if (Number.isFinite(fraction)) {
      const fill = element("span", "compare-measure-fill");
      fill.style.width = fraction + "%";
      track.append(fill);
    } else {
      track.dataset.unverified = "";
    }
    return track;
  }

  function coverageChart(row, key, footprintMax) {
    const chart = chartButton(row, key);
    const field = key + "_area_m2";
    if (key === "object") {
      const area = areaValue(row, field);
      chart.classList.add("compare-footprint-chart");
      const exact = readableArea(row, field);
      chart.append(measureTrack(footprintMax > 0 ? 100 * area / footprintMax : NaN),
        element("strong", "compare-chart-value", exact));
      chart.setAttribute("aria-label", chart.getAttribute("aria-label") + ", " + exact);
      return chart;
    }
    const activity = key === "activity";
    const share = shareOfActivity(row, activity ? "object_area_m2" : field);
    const pie = pieGraphic([[share,"atlas-pie-slice"]]);
    if (!Number.isFinite(share) || share < 0 || share > 100) pie.setAttribute("hidden", "");
    const label = {activity:"F / A", part:"Parts", human:"Human", machine:"Machine"}[key];
    chart.append(element("span", "compare-chart-label", label), pie,
      element("strong", "compare-chart-share", readableShare(share)),
      element("span", "compare-chart-value", readableArea(row, field)));
    if (activity) chart.append(element("span", "compare-chart-ratio", "A/F " + multiplier(row)));
    chart.setAttribute("aria-label", chart.getAttribute("aria-label") +
      `, ${readableArea(row, field)}, ${readableShare(share)} ${activity ? "F over A" : "of A"}`);
    return chart;
  }

  function studyRow(study, pair, plans, shared) {
    const {mode, name, keys} = study;
    const label = comparisonLabel(study, pair);
    const middle = element("div", "compare-charts");
    const footprintMax = pair.every(hasMetres) ? Math.max(...pair.map(row => areaValue(row,"object_area_m2"))) : NaN;
    const sides = pair.map((row, index) => {
      const plan = renderPlan(row, plans[index], shared, mode, name);
      const side = element("div", "compare-plan");
      side.append(plan);
      const charts = element("div", "compare-case-charts");
      const controls = keys.map(key => [coverageChart(row, key, footprintMax), key]);
      for (const [chart] of controls) charts.append(chart);
      bindHighlights(controls, plan);
      middle.append(charts);
      return side;
    });
    const row = rowLayout(label, sides[0], middle, sides[1]);
    row.dataset.compareRow = mode;
    return row;
  }

  function modelComparison(pair, metrics, plans) {
    const label = element("div", "");
    label.append(element("h3", "", "Finished members"));
    const measures = [
      {name:"Main members", unit:"pcs", value:item => item?.members, featured:true},
      {name:"Height", unit:"m", value:item => item?.dimensions?.[2], approximate:true},
      {name:"Solid volume", unit:"m³", value:item => item?.volume},
      {name:"Member surface", unit:"m²", value:item => item?.surface}
    ];
    const middle = element("div", "compare-model-metrics");
    middle.append(element("p", "compare-metric-caption", "Share of the pair"));
    for (const {name, unit, value, featured, approximate} of measures) {
      const values = metrics.map(value);
      const total = values.every(Number.isFinite) ? values[0] + values[1] : NaN;
      const measure = element("div", "compare-measure");
      if (featured) measure.classList.add("compare-measure-featured");
      const pairValues = element("div", "compare-measure-values");
      values.forEach((amount, index) => {
        const fraction = total > 0 ? 100 * amount / total : NaN;
        const item = element("div", "compare-measure-value");
        const isApproximate = approximate || (unit !== "pcs" && metrics[index]?.approximate);
        const exact = modelNumber(amount, unit, isApproximate);
        if (Number.isFinite(fraction)) {
          item.append(element("strong", "", readableShare(fraction)));
        } else {
          item.append(element("strong", "", "—"));
        }
        item.append(measureTrack(fraction), element("span", "compare-chart-value", exact));
        item.setAttribute("aria-label", pair[index].case + ": " + exact);
        pairValues.append(item);
      });
      measure.append(element("h4", "", name), pairValues);
      middle.append(measure);
    }
    const cards = pair.map((row, index) => metricCard(row, metrics[index], plans[index]));
    const row = rowLayout(label, cards[0], middle, cards[1]);
    row.dataset.compareRow = "model";
    return row;
  }

  function caseFindings(pair) {
    const key = pair.map(row => row.case).sort().join("-");
    if (findingsByPair[key]) return findingsByPair[key];
    if (!pair.every(hasMetres)) {
      return pair.map(row => `${row.case} records activity across ${multiplier(row)} its finished footprint.`).join(" ");
    }
    const [first, second] = pair;
    const area = (row, kind) => readableArea(row, kind + "_area_m2");
    const [greater] = [...pair].sort((a,b) => areaValue(b,"part_area_m2") - areaValue(a,"part_area_m2"));
    const partNote = areaValue(first,"part_area_m2") === areaValue(second,"part_area_m2")
      ? "Recorded part coverage is equal." : `${greater.case} records the wider part movement area.`;
    return `The finished footprints are ${area(first,"object")} for ${first.case} and ${area(second,"object")} for ${second.case}. Total activity covers ${area(first,"activity")} and ${area(second,"activity")}, respectively. ${partNote}`;
  }

  function readComparison(source, rows, registered, modelMetrics, outlines) {
    const picked = ["#compare-first","#compare-second"].map(selector => atlas.querySelector(selector));
    const byId = new Map(rows.map(row => [row.case, row]));
    const planCache = new Map();
    const matrix = atlas.querySelector("#compare-matrix");
    const detail = atlas.querySelector("#atlas-pair-detail");
    const common = atlas.querySelector("#atlas-common");
    const defaults = ["V01","V24"];
    const params = new URLSearchParams(location.search);
    const initial = params.has("first") || params.has("second") ? [params.get("first"),params.get("second")] : defaults;

    for (const [index, select] of picked.entries()) {
      select.add(new Option("Choose a case", ""));
      for (const row of rows) select.add(new Option(row.case, row.case));
      const id = initial[index];
      if (byId.has(id) && (index === 0 || id !== initial[0])) select.value = id;
      select.addEventListener("change", () => {
        history.replaceState(null, "", compareUrl(picked.map(input => input.value)));
        renderComparison();
      });
    }
    common.addEventListener("change", renderComparison);

    function renderComparison() {
      const pair = picked.map(select => byId.get(select.value));
      for (const [index, select] of picked.entries()) {
        const other = picked[1-index].value;
        for (const option of select.options) option.disabled = Boolean(option.value) && option.value === other;
      }
      detail.hidden = !pair.every(Boolean);
      atlas.querySelector("#compare-empty").hidden = !detail.hidden;
      if (detail.hidden) {
        document.title = "Compare two cases · Atlas of Assembly Space";
        return;
      }
      const title = pair.map(row => row.case).join(" ↔ ");
      document.title = title + " · Compare two cases";
      atlas.querySelector("#atlas-pair-heading").textContent = title;
      const plans = pair.map(row => {
        if (!planCache.has(row.case)) {
          const plan = getPlan(source, row, registered, outlines);
          planCache.set(row.case, {...plan, viewBox:areaPlanBox(plan)});
        }
        return planCache.get(row.case);
      });
      const canShare = plans.every(plan => plan.metres);
      common.disabled = !canShare;
      common.closest("label").hidden = !canShare;
      const shared = canShare && common.checked ? {
        width:Math.max(...plans.map(plan => plan.viewBox[2] * plan.metres)),
        height:Math.max(...plans.map(plan => plan.viewBox[3] * plan.metres))
      } : null;
      atlas.querySelector("#atlas-plan-note").textContent = shared ? "Top Views share a metre scale" : "Top Views fitted separately";
      const chartLabels = element("div", "compare-chart-headings");
      chartLabels.append(...pair.map(row => element("span", "", row.case)));
      const heading = rowLayout(element("div", ""), caseLink(pair[0]), chartLabels, caseLink(pair[1]));
      heading.classList.add("compare-matrix-heading");
      const metrics = pair.map(row => modelMetrics[row.case]);
      matrix.replaceChildren(heading, ...studyRows.map(study => studyRow(study, pair, plans, shared)),
        modelComparison(pair, metrics, plans));
      atlas.querySelector("#compare-findings").textContent = caseFindings(pair);
    }
    renderComparison();
  }

  async function load() {
    const response = await fetch(casePage);
    if (!response.ok) throw new Error("Case page: " + response.status);
    const source = document.createElement("template");
    source.innerHTML = await response.text();
    const data = JSON.parse(source.content.querySelector("#ma-data").textContent);
    if (comparisonPage) {
      const [registration, modelMetrics, outlines] = await Promise.all([
        fetch("case_area_comparison.csv").then(response => response.ok ? response.text() : "").catch(() => ""),
        fetch("case-model-metrics.json?v=2").then(response => response.ok ? response.json() : {}).catch(() => ({})),
        fetch("case-plan-outlines.json?v=1").then(response => response.ok ? response.json() : {}).catch(() => ({}))
      ]);
      const registered = new Set();
      for (const line of registration.split(/\r?\n/)) {
        const id = line.match(/^"?(V\d+)"?,/)?.[1];
        if (id && line.includes('"registered metric union"')) registered.add(id);
      }
      readComparison(source.content, data.rows, registered, modelMetrics, outlines);
    } else {
      readAtlas(data);
    }
    atlas.querySelector("#atlas-status").hidden = true;
    atlas.querySelector("#atlas-content").hidden = false;
  }

  load().catch(error => {
    console.error(error);
    atlas.querySelector("#atlas-status").textContent = "Could not load the case measurements. Reload the page to try again.";
  });
})();

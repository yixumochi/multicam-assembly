(() => {
  const atlas = document.getElementById("atlas");
  const casePage = new URL("../index.html", location.href);
  const metric = row => row.unit === "mm_to_m";
  const calibration = row => metric(row) ? undefined : areaCalibration[row.case];
  const hasMetres = row => metric(row) || Boolean(calibration(row));
  const unit = row => hasMetres(row) ? "m²" : "model units²";
  const scale = reference => reference.referenceMetres / reference.bounds[reference.axis];
  const areaFields = ["activity", "object", "human", "machine", "part"].map(key => key + "_area_m2");
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

  function axis(maximum, label) {
    const node = element("div", "atlas-axis");
    for (let tick = 0; tick <= 4; tick++) {
      const suffix = label === "%" ? label : tick === 4 ? " " + label : "";
      node.append(element("span", "", (maximum * tick / 4).toLocaleString("en") + suffix));
    }
    return node;
  }

  function bars(maximum, fields) {
    const node = element("div", "atlas-bars");
    for (const {key, label, value, caption} of fields) {
      const line = element("div", "atlas-bar-line");
      const track = element("span", "atlas-track");
      const fill = element("span", "atlas-fill " + key);
      fill.style.width = (Number.isFinite(value) ? 100 * value / maximum : 0) + "%";
      track.append(fill);
      line.append(element("b", "atlas-bar-label", label), track, element("span", "atlas-value", caption));
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

  function renderPlan(row, {plan, data, viewBox, metres}, shared, layers, highlighted) {
    const panel = element("article", "atlas-card");
    const title = caseHeading(row);
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
    if (highlighted) {
      const points = highlighted.line;
      const radius = Math.min(width, height) * 0.023;
      geometry.append(svgElement("polyline", {
        points:coordinates(points), class:"role-highlight", fill:"none"
      }));
      for (const [index, point] of [points[0], points.at(-1)].entries()) {
        const [x, y] = point;
        geometry.append(svgElement("circle", {cx:x, cy:y, r:radius, class:"role-endpoint"}));
        const number = svgElement("text", {
          x, y, "dominant-baseline":"central", "text-anchor":"middle", "font-size":radius * 1.15,
          class:"role-endpoint-label"
        });
        number.textContent = index + 1;
        geometry.append(number);
      }
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

  function caseHeading(row) {
    const heading = element("h4");
    const link = element("a", "", row.case + " case sheet");
    link.href = caseUrl(row);
    heading.append(link);
    return heading;
  }

  function metricCard(row, metrics) {
    const card = element("article", "atlas-card");
    const facts = element("dl", "pair-study-facts");
    const number = (value, unit, approximate = false) => Number.isFinite(value)
      ? (approximate ? "≈" : "") + value.toLocaleString("en", {maximumFractionDigits:unit === "m³" ? 3 : 1}) + " " + unit
      : "Unverified";
    for (const [name, value] of [["Main members", number(metrics?.members, "pcs")],
      ["Solid member volume", number(metrics?.volume, "m³", metrics?.approximate)],
      ["Member surface area", number(metrics?.surface, "m²", metrics?.approximate)]]) {
      facts.append(element("dt", "", name), element("dd", "", value));
    }
    card.append(caseHeading(row), facts);
    if (metrics) card.append(element("p", "note", metrics.scope), element("p", "note pair-study-model-source", metrics.file));
    return card;
  }

  function partExample(row, plan) {
    const [x, y, width, height] = plan.viewBox;
    const visible = point => point[0] >= x && point[0] <= x+width && point[1] >= y && point[1] <= y+height;
    const candidates = plan.data.actions.filter(action => action.role === "part" && action.line?.length > 1 &&
      action.end.time > action.start.time && [action.line[0], action.line.at(-1)].every(visible));
    const chosen = candidates.find(action => action.id === {V01:"065", V24:"102"}[row.case]);
    const travel = ({line}) => Math.hypot(line.at(-1)[0]-line[0][0], line.at(-1)[1]-line[0][1]);
    return chosen || candidates.sort((a,b) => travel(b)-travel(a)).find(action => travel(action) > 0);
  }

  function coveragePie(row, key, label) {
    const field = key + "_area_m2";
    const share = shareOfActivity(row, field);
    const item = element("figure", "atlas-coverage-pie");
    item.dataset.coverageRole = key;
    const pie = svgElement("svg", {viewBox:"0 0 80 80",class:"atlas-pie-svg","aria-hidden":"true"});
    pie.append(svgElement("circle", {cx:40,cy:40,r:36,class:"atlas-pie-base"}));
    if (share === 100) {
      pie.append(svgElement("circle", {cx:40,cy:40,r:36,class:"atlas-pie-slice"}));
    } else if (share > 0 && share < 100) {
      const theta = 2 * Math.PI * share / 100;
      const x = 40 + 36*Math.sin(theta);
      const y = 40 - 36*Math.cos(theta);
      pie.append(svgElement("path", {class:"atlas-pie-slice",d:`M 40 40 L 40 4 A 36 36 0 ${share > 50 ? 1 : 0} 1 ${x} ${y} Z`}));
    }
    const caption = element("figcaption");
    caption.append(element("span", "atlas-pie-label", label),
      element("strong", "atlas-share-value", readableShare(share)),
      element("span", "atlas-share-area", readableArea(row, field)));
    if (!Number.isFinite(share) || share < 0 || share > 100) pie.setAttribute("hidden", "");
    item.append(pie, caption);
    return item;
  }

  function start(source, {rows, modes}, registered, modelMetrics) {
    const metricLimit = Math.ceil(Math.max(20, ...rows.filter(hasMetres)
      .flatMap(row => areaFields.map(field => areaValue(row, field)))) / 20) * 20;
    const modelLimit = row => Math.ceil(Math.max(10, ...areaFields.map(field => row[field])) / 10) * 10;
    const first = atlas.querySelector("#compare-first");
    const second = atlas.querySelector("#compare-second");
    const question = atlas.querySelector("#compare-question");
    const roleChoice = atlas.querySelector("#compare-role");
    const roleControl = atlas.querySelector("#compare-role-control");
    const areaStudy = atlas.querySelector("#atlas-area-study");
    const operatorPlans = atlas.querySelector("#compare-operators");
    const partPlans = atlas.querySelector("#compare-parts");
    const modelCards = atlas.querySelector("#compare-models");
    const modelReading = atlas.querySelector("#compare-model-reading");
    const planCache = new Map();
    const planFor = row => {
      if (!planCache.has(row.case)) planCache.set(row.case, getPlan(source, row, registered));
      return planCache.get(row.case);
    };
    const byId = new Map(rows.map(row => [row.case, row]));
    const compareLayers = [...atlas.querySelectorAll(".atlas-layers input[value]")];
    const picked = [first, second];
    const detail = atlas.querySelector("#atlas-pair-detail");
    for (const select of picked) {
      select.add(new Option("Choose a case", ""));
      for (const row of rows) select.add(new Option(row.case, row.case));
    }
    let selectedRelation = null;

    const roleNames = {human:"Human", machine:"Machine", part:"Parts"};
    const roleAdvice = {
      human:"Follow the paths people use to approach and move alongside the assembly.",
      machine:"Follow how far the machine moves around the object.",
      part:"Follow the routes parts take as they enter and turn near the object."
    };
    const fieldRows = (row, specs) => specs.map(([field, key, label]) => ({
      key, label, value:areaValue(row, field + "_area_m2"), caption:readableArea(row, field + "_area_m2")
    }));

    function studyPlan(row, plan, shared, layers, highlighted) {
      const card = renderPlan(row, plan, shared, new Set(layers), highlighted);
      card.querySelector("svg image").setAttribute("opacity", "0.84");
      const pies = element("div", "atlas-coverage-pies");
      for (const key of layers) pies.append(coveragePie(row, key, roleNames[key]));
      card.querySelector("svg").before(pies);
      if (highlighted) {
        const timing = element("p", "note pair-study-timing");
        const marks = [highlighted.start, highlighted.end];
        marks.forEach((mark, index) => {
          const text = `${index+1} · ${mark.time.toFixed(1)} s`;
          const frame = element(mark.src ? "a" : "span", "", text);
          if (mark.src) frame.href = new URL(mark.src, casePage).href;
          timing.append(frame);
        });
        card.append(timing);
      }
      return card;
    }

    function renderComparison() {
      const pair = picked.map(select => byId.get(select.value));
      for (const select of picked) {
        const other = select === first ? second : first;
        for (const option of select.options) option.disabled = Boolean(option.value) && option.value === other.value;
      }
      relationAtlas.update(picked.map(select => select.value), selectedRelation);
      roleControl.hidden = question.value !== "role";
      detail.hidden = !pair.every(Boolean);
      if (detail.hidden) return;
      const compareBars = atlas.querySelector("#compare-bars");
      const plans = atlas.querySelector("#compare-plans");
      compareBars.replaceChildren();
      plans.replaceChildren();
      const findings = atlas.querySelector("#compare-findings");
      const selectedRole = roleChoice.value;
      const field = selectedRole + "_area_m2";
      const metricPair = pair.every(hasMetres);
      const roleShare = row => shareOfActivity(row, field);
      const roleMode = question.value === "role";
      const studyMode = question.value === "summary";
      atlas.querySelector("#atlas-pair-key").hidden = !studyMode;
      areaStudy.hidden = !studyMode;
      plans.hidden = studyMode;
      for (const input of compareLayers) {
        input.closest("label").hidden = roleMode || studyMode;
        input.disabled = roleMode || studyMode;
      }
      let fieldsFor;
      let extent;
      let axisUnit;
      if (studyMode) {
        findings.textContent = selectedRelation?.finding || (metricPair
          ? `${pair[0].case} recorded ${readableArea(pair[0], "activity_area_m2")} of activity and ${pair[1].case} recorded ${readableArea(pair[1], "activity_area_m2")}. Compare their A/F and role coverage below.`
          : "A/F is comparable across units. Each case uses its own area scale below.");
        const peak = Math.max(...pair.flatMap(row => areaFields.map(field => areaValue(row,field))));
        const increment = peak <= 10 ? 2 : peak <= 40 ? 5 : 10;
        extent = metricPair ? Math.max(increment, Math.ceil(peak/increment)*increment) : null;
        axisUnit = "m²";
        fieldsFor = row => fieldRows(row, [["object", "footprint", "F"], ["activity", "activity", "A"]]);
      } else if (question.value === "ratio") {
        const ratio = row => row.ratio_activity_over_object;
        const [higher, lower] = [...pair].sort((left,right) => ratio(right)-ratio(left));
        const answer = ratio(higher) === ratio(lower)
          ? "Both cases have the same A/F."
          : `${higher.case} spreads further relative to its finished size (${multiplier(higher)} vs ${multiplier(lower)}).`;
        const footprint = metricPair
          ? ` Compare their finished footprints too (${readableArea(higher,"object_area_m2")} vs ${readableArea(lower,"object_area_m2")}).` : "";
        findings.textContent = answer + footprint;
        extent = Math.ceil(Math.max(...pair.map(ratio)) / 4) * 4;
        axisUnit = "×";
        fieldsFor = row => [{key:"activity", label:"A/F", value:ratio(row), caption:multiplier(row)}];
      } else if (roleMode) {
        const [higher, lower] = [...pair].sort((left,right) => roleShare(right)-roleShare(left));
        const percentage = row => readableShare(roleShare(row));
        const answer = roleShare(higher) === roleShare(lower)
          ? `${roleNames[selectedRole]} tracks cover the same share in both cases (${percentage(higher)}).`
          : `${roleNames[selectedRole]} tracks cover a larger share in ${higher.case} (${percentage(higher)} vs ${percentage(lower)} in ${lower.case}).`;
        findings.textContent = answer + " " + roleAdvice[selectedRole];
        extent = 100;
        axisUnit = "%";
        fieldsFor = row => [{key:"activity",label:"A %",value:roleShare(row),caption:percentage(row)}];
      } else {
        const area = row => areaValue(row,"activity_area_m2");
        const [larger, smaller] = [...pair].sort((left,right) => area(right)-area(left));
        findings.textContent = metricPair
          ? (area(larger) === area(smaller)
            ? "Both cases cover the same area during assembly."
            : `${larger.case} covers more area during assembly (${readableArea(larger,"activity_area_m2")} vs ${readableArea(smaller,"activity_area_m2")}).`)
          : "Switch to the relative-size question to compare cases with different units.";
        extent = metricPair ? metricLimit : null;
        axisUnit = "m²";
        fieldsFor = row => [{key:"activity",label:"A",value:area(row),caption:readableArea(row,"activity_area_m2")}];
      }
      const planData = pair.map(planFor);
      const common = atlas.querySelector("#atlas-common");
      const canShare = planData.every(plan => plan.metres);
      common.disabled = !canShare;
      common.closest("label").hidden = studyMode && !canShare;
      const shared = canShare && common.checked ? {
        width:Math.max(...planData.map(plan => plan.viewBox[2]*plan.metres)),
        height:Math.max(...planData.map(plan => plan.viewBox[3]*plan.metres))
      } : null;
      const layers = new Set(roleMode ? [selectedRole] : compareLayers.filter(input => input.checked).map(input => input.value));
      atlas.querySelector("#atlas-plan-note").textContent = "Top Views from Fifteen assembly cases. The dashed outline marks the finished object’s bounds. " +
        (shared ? "Both plans use the same scale." : "Each plan is fitted to its own view.");
      operatorPlans.replaceChildren();
      partPlans.replaceChildren();
      modelCards.replaceChildren();
      const firstExample = studyMode && pair.some(row => row.case === "V01") && pair.some(row => row.case === "V24");
      const counts = [modelMetrics.V01?.members, modelMetrics.V24?.members];
      modelReading.hidden = !firstExample || !counts.every(Number.isFinite);
      if (!modelReading.hidden) {
        modelReading.textContent = `V24 has ${(counts[1]/counts[0]).toFixed(1)} times as many modeled main members. V01 covers ${(
          areaValue(byId.get("V01"), "activity_area_m2")/areaValue(byId.get("V24"), "activity_area_m2")).toFixed(1)} times the recorded activity area.`;
      }
      pair.forEach((row, index) => {
        const card = element("article", "atlas-card");
        const maximum = extent || (hasMetres(row) ? metricLimit : modelLimit(row));
        card.append(caseHeading(row), bars(maximum, fieldsFor(row)), axis(maximum, extent ? axisUnit : unit(row)));
        compareBars.append(card);
        if (studyMode) {
          const ratios = element("p", "atlas-pair-ratio");
          ratios.append(element("span", "", "A/F  " + multiplier(row)),
            element("span", "atlas-inverse-ratio", "F/A  " + readableShare(shareOfActivity(row, "object_area_m2"))));
          card.append(ratios);
          const plan = planData[index];
          operatorPlans.append(studyPlan(row, plan, shared, ["human","machine"]));
          partPlans.append(studyPlan(row, plan, shared, ["part"], partExample(row,plan)));
          modelCards.append(metricCard(row,modelMetrics[row.case]));
        } else {
          plans.append(renderPlan(row, planData[index], shared, layers));
        }
      });
    }

    const relationAtlas = initializeCaseRelations({rows, modes, hasMetres, areaValue, calibration, readableArea,
      chooseCase(id) {
        selectedRelation = null;
        question.value = "summary";
        const complete = Boolean(first.value && second.value);
        if (complete || id === first.value || id === second.value) {
          first.value = id;
          second.value = "";
        } else if (!first.value) {
          first.value = id;
        } else {
          second.value = id;
        }
        renderComparison();
        if (!detail.hidden) atlas.querySelector("#atlas-pair-heading").focus();
      },
      chooseRelation(relation) {
        selectedRelation = relation;
        question.value = "summary";
        first.value = relation.ids[0];
        second.value = relation.ids[1];
        renderComparison();
        atlas.querySelector("#atlas-pair-heading").focus();
      }
    });
    renderComparison();
    for (const select of picked) select.addEventListener("change", () => {
      selectedRelation = null;
      renderComparison();
    });
    for (const control of [question,roleChoice]) control.addEventListener("change", renderComparison);
    atlas.querySelector(".atlas-layers").addEventListener("change", renderComparison);
    atlas.querySelector("#atlas-status").hidden = true;
    atlas.querySelector("#atlas-content").hidden = false;
    initializeSpatialRoles({
      rows, modes, median, caseUrl, areaValue, calibration,
      showPlan(row, role, selectTrack) {
        const plan = planFor(row);
        const track = selectTrack(plan.data.actions.filter(action => action.role === role), plan.viewBox);
        return {drawing: renderPlan(row, plan, null, new Set([role]), track), track};
      },
      frameUrl: name => name ? new URL(name, casePage).href : null
    });
  }

  async function load() {
    const [response, registration, modelMetrics] = await Promise.all([
      fetch(casePage),
      fetch("case_area_comparison.csv").catch(() => null),
      fetch("case-model-metrics.json?v=1").then(result => result.ok ? result.json() : {}).catch(() => ({}))
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
    start(source.content, areaData, registered, modelMetrics);
  }

  load().catch(error => {
    console.error(error);
    for (const status of [atlas.querySelector("#atlas-status"), document.getElementById("roles-status")]) {
      status.textContent = "Could not load the case measurements. Reload the page to try again.";
    }
  });
})();

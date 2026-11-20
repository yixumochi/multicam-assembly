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

  function axis(maximum, label, intervals = 4) {
    const node = element("div", "atlas-axis");
    for (let tick = 0; tick <= intervals; tick++) {
      const suffix = label === "%" ? label : tick === intervals ? " " + label : "";
      const mark = element("span", "", (maximum * tick / intervals).toLocaleString("en") + suffix);
      mark.style.setProperty("--tick", `${100 * tick / intervals}%`);
      node.append(mark);
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

  function filledCoverage(geometry, actions, layers, caseId) {
    const byRole = new Map();
    for (const action of actions) {
      if (!layers.has(action.role) || (action.poly?.length ?? 0) < 3) continue;
      const signedArea = action.poly.reduce((sum, [x,y], index, points) => {
        const [nextX,nextY] = points[(index+1)%points.length];
        return sum + x*nextY - nextX*y;
      },0);
      if (!Number.isFinite(signedArea) || signedArea === 0) continue;
      const ring = signedArea > 0 ? action.poly : [...action.poly].reverse();
      byRole.set(action.role, (byRole.get(action.role) || "") + `M ${coordinates(ring)} Z `);
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

  function renderPlan(row, {plan, data, viewBox, metres, outline}, shared, layers, {highlighted, coverageOnly = false, switchable = false} = {}) {
    const panel = element("article", "atlas-card");
    const title = caseHeading(row, coverageOnly);
    const [left, top, width, height] = viewBox;
    const canvas = svgElement("svg", {
      viewBox: shared ? `0 0 ${shared.width} ${shared.height}` : viewBox.join(" "),
      role: "img", "aria-label": row.case + (coverageOnly ? " original top drawing and activity coverage" : " original top drawing and selected activity tracks")
    });
    const geometry = svgElement("g", {});
    if (shared) {
      const offsetX = (shared.width - width * metres) / 2;
      const offsetY = (shared.height - height * metres) / 2;
      geometry.setAttribute("transform", `translate(${offsetX} ${offsetY}) scale(${metres}) translate(${-left} ${-top})`);
    }
    const backdrop = plan.querySelector("image").cloneNode(true);
    backdrop.setAttribute("href", new URL(backdrop.getAttribute("href"), casePage).href);
    backdrop.setAttribute("opacity", switchable ? (outline ? "0.48" : "0.7") : coverageOnly ? "1" : "0.55");
    if (coverageOnly) {
      geometry.classList.add("atlas-coverage-plan");
      backdrop.classList.add("atlas-coverage-drawing");
      if (switchable) {
        for (const [mode, roles] of [["operators", ["human","machine"]], ["parts", ["part"]]]) {
          const layer = svgElement("g", {"data-study-layer":mode});
          filledCoverage(layer, data.actions, new Set(roles), row.case);
          geometry.append(layer);
        }
      } else {
        filledCoverage(geometry,data.actions,layers,row.case);
      }
      geometry.append(backdrop);
      if (switchable && outline) geometry.append(svgElement("path", {
        d:`M ${coordinates(outline)} Z`, class:"atlas-object-outline"
      }));
    } else {
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
    }
    if (!coverageOnly && data.object_range) {
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
    panel.append(title, canvas);
    if (!coverageOnly) panel.append(element("p", "note", shared ? "Shared metre scale" : "Fit to saved plan · " + (metric(row) ? "metric case" : "model units")));
    return panel;
  }

  function median(values) {
    const ordered = [...values].sort((left, right) => left - right);
    const middle = Math.floor(ordered.length / 2);
    return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
  }

  function caseHeading(row, compact = false) {
    const heading = element("h4");
    const link = element("a", "", compact ? row.case : row.case + " case sheet");
    if (compact) link.setAttribute("aria-label", row.case + " case sheet");
    link.href = caseUrl(row);
    heading.append(link);
    return heading;
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
    const card = element("article", "atlas-card");
    card.append(caseHeading(row, true));
    if (plan.iso) {
      const figure = element("figure", "pair-study-iso");
      const image = element("img");
      image.src = new URL(plan.iso, casePage).href;
      image.alt = row.case + " isometric view from Fifteen assembly cases";
      const pose = metrics?.dimensionPose ? ` (${metrics.dimensionPose})` : "";
      const height = metrics?.dimensions ? " · Height " + modelNumber(metrics.dimensions[2], "m", true) + pose : "";
      figure.append(image, element("figcaption", "", "ISO" + height));
      card.append(figure);
    }
    const facts = element("dl", "pair-study-facts");
    for (const [name, value] of [["Main members", modelNumber(metrics?.members, "pcs")],
      ["Dimensions (X × Y × Z)", modelDimensions(metrics)],
      ["Solid member volume", modelNumber(metrics?.volume, "m³", metrics?.approximate)],
      ["Member surface area", modelNumber(metrics?.surface, "m²", metrics?.approximate)]]) {
      facts.append(element("dt", "", name), element("dd", "", value));
    }
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

  function coveragePie(row, key, label) {
    const field = key + "_area_m2";
    const share = shareOfActivity(row, field);
    const item = element("figure", "atlas-coverage-pie");
    item.dataset.coverageRole = key;
    const pie = pieGraphic([[share,"atlas-pie-slice"]]);
    const caption = element("figcaption");
    caption.append(element("span", "atlas-pie-label", label),
      element("strong", "atlas-share-value", readableShare(share)),
      element("span", "atlas-share-area", readableArea(row, field)));
    if (!Number.isFinite(share) || share < 0 || share > 100) pie.setAttribute("hidden", "");
    item.append(pie, caption);
    return item;
  }

  function renderMemberPie(container, pair, metrics) {
    const counts = metrics.map(item => item?.members);
    container.hidden = !counts.every(count => Number.isFinite(count) && count > 0);
    container.replaceChildren();
    if (container.hidden) return;
    const total = counts[0] + counts[1];
    const shares = [100*counts[0]/total,100*counts[1]/total];
    const colors = ["atlas-member-first", "atlas-member-second"];
    const figure = element("figure", "atlas-member-pie atlas-coverage-pie");
    const caption = element("figcaption");
    caption.append(element("b", "", "Main members · share of both counts"));
    pair.forEach((row, index) => caption.append(element("span", "atlas-member-key " + colors[index],
      `${row.case} · ${counts[index]} pcs · ${readableShare(shares[index])}`)));
    figure.append(pieGraphic(shares.map((share,index) => [share,"atlas-pie-slice " + colors[index]])), caption);
    container.append(figure);
  }

  const summaryRowsByPair = {
    "V01-V24": ["Footprint", "Parts", "Main members"],
    "V11-V26": ["Footprint", "Total activity", "Parts"],
    "V20-V22": ["Total activity", "Human", "Machine"],
    "V04-V28": ["Footprint", "Total activity", "Parts"],
    "V27-V29": ["Parts", "Human", "Machine"]
  };

  function renderPairSummary(container, pair, metrics, plans, conclusion) {
    const comparableArea = pair.every(hasMetres);
    const area = key => row => comparableArea ? areaValue(row, key + "_area_m2") : NaN;
    const rows = {
      "Footprint": ["footprint",area("object"),"m²","M3 6h22v16H3z"],
      "Total activity": ["ink",area("activity"),"m²","M7 7Q1 10 5 17Q8 23 17 21Q27 19 24 11Q22 4 16 7Q12 9 7 7Z"],
      "Activity per footprint": ["ink",row => row.ratio_activity_over_object,"×","M4 4h20v20H4z M10 10h8v8h-8z"],
      "Human": ["human",area("human"),"m²","M14 3a3 3 0 1 0 0 6a3 3 0 0 0 0-6 M14 10v7 M7 13h14 M14 17l-5 8 M14 17l5 8"],
      "Machine": ["machine",area("machine"),"m²","M4 24h14 M8 24v-5l7-8 M15 11l5 4 M20 15v4 M22 17h-4 M15 9a2 2 0 1 0 .01 0"],
      "Parts": ["part",area("part"),"m²","M3 16l16-9 4 5-16 9z M7 21v3l16-9v-3 M3 16v3l4 5 M7 6h17 M21 3l3 3-3 3"],
      "Main members": ["ink",(row,item) => item?.members,"pcs","M4 5h8v7H4z M16 5h8v7h-8z M4 16h8v7H4z M16 16h8v7h-8z"]
    };
    const key = pair.map(row => row.case).sort().join("-");
    const fallback = comparableArea ? ["Footprint", "Total activity", "Parts"] : ["Activity per footprint", "Main members"];
    const selection = summaryRowsByPair[key] ?? fallback;
    const svg = svgElement("svg", {viewBox:`0 0 760 ${164 + selection.length * 48}`, role:"img", class:"pair-summary-graphic",
      "aria-label":`Comparison of ${pair[0].case} and ${pair[1].case}`, "aria-describedby":"pair-summary-description"});
    const description = svgElement("desc", {id:"pair-summary-description"});
    const readout = [conclusion, "Bars compare the two cases within each row."];
    svg.append(description);
    plans.forEach((plan, index) => {
      if (plan.iso) svg.append(svgElement("image", {x:index ? 422 : 28,y:4,width:310,height:146,
        href:new URL(plan.iso,casePage).href}));
    });
    svg.append(svgElement("path", {d:"M 28 158 H 338 M 422 158 H 732",class:"pair-summary-rule"}));
    for (const [index, label] of selection.entries()) {
      const [color, measure, unitName, icon] = rows[label];
      const y = 187 + index * 48;
      const line = svgElement("g", {"data-summary-metric":label,"data-summary-tone":color});
      const values = pair.map((row,index) => measure(row,metrics[index]));
      const peak = Math.max(...values.filter(Number.isFinite),0);
      line.append(svgElement("path", {d:icon,transform:`translate(366 ${y-14})`,class:"pair-summary-icon"}));
      values.forEach((value,index) => {
        const x = index ? 422 : 28;
        line.append(svgElement("rect", {x,y:y-9,width:310,height:18,rx:2,class:"pair-summary-track"}));
        if (Number.isFinite(value) && value > 0) {
          const width = 310*value/peak;
          line.append(svgElement("rect", {x:index ? x : 338-width,y:y-9,width,height:18,rx:2,class:"pair-summary-value"}));
        } else if (!Number.isFinite(value)) {
          line.append(svgElement("path", {d:`M ${x+134} ${y} h42`,class:"pair-summary-missing"}));
        }
      });
      readout.push(`${label}: ${pair.map((row,index) => `${row.case} ${modelNumber(values[index],unitName,unitName === "m²" && calibration(row))}`).join(", ")}.`);
      svg.append(line);
    }
    description.textContent = readout.join(" ");
    container.replaceChildren(svg);
  }

  function start(source, {rows, modes}, registered, modelMetrics, outlines) {
    const metricLimit = Math.ceil(Math.max(20, ...rows.filter(hasMetres)
      .flatMap(row => areaFields.map(field => areaValue(row, field)))) / 20) * 20;
    const modelLimit = row => Math.ceil(Math.max(10, ...areaFields.map(field => row[field])) / 10) * 10;
    const first = atlas.querySelector("#compare-first");
    const second = atlas.querySelector("#compare-second");
    const question = atlas.querySelector("#compare-question");
    const roleChoice = atlas.querySelector("#compare-role");
    const roleControl = atlas.querySelector("#compare-role-control");
    const areaStudy = atlas.querySelector("#atlas-area-study");
    const coveragePlans = atlas.querySelector("#compare-coverage");
    const layerButtons = [...atlas.querySelectorAll("[data-study-mode]")];
    const modelCards = atlas.querySelector("#compare-models");
    const memberPie = atlas.querySelector("#compare-member-pie");
    const summary = atlas.querySelector("#compare-summary");
    const planCache = new Map();
    const planFor = row => {
      if (!planCache.has(row.case)) planCache.set(row.case, getPlan(source, row, registered, outlines));
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
    let lastPair = "";
    let studyLayer = "operators";

    const roleNames = {human:"Human", machine:"Machine", part:"Parts"};
    const roleAdvice = {
      human:"Follow the paths people use to approach and move alongside the assembly.",
      machine:"Follow how far the machine moves around the object.",
      part:"Follow the routes parts take as they enter and turn near the object."
    };
    const conclusions = {
      "V01-V24":"V01 uses more recorded assembly space at a similar footprint. V24 has more modeled members. Check the range of part handling separately from the member count.",
      "V11-V26":"The finished footprints are close. V11 records more total and part activity, and machine coverage is the larger measured layer in V26. The two layouts call for different checks around the finished object.",
      "V20-V22":"The cases cover almost the same total area. V20 records human movement and V22 records machine movement. The top views show which routes to check in each layout.",
      "V04-V28":"The total activity areas are close. Parts cover a larger share of A in V28, so its part routes are especially useful for reading the extent of the work area.",
      "V27-V29":"Part coverage is close in square metres. Human coverage is larger in V27, and machine coverage is larger in V29. Read the part routes together with the different operator routes."
    };
    const fieldRows = (row, specs) => specs.map(([field, key, label]) => ({
      key, label, value:areaValue(row, field + "_area_m2"), caption:readableArea(row, field + "_area_m2")
    }));

    function setStudyLayer(mode) {
      studyLayer = mode;
      for (const button of layerButtons) button.setAttribute("aria-pressed", String(button.dataset.studyMode === mode));
      for (const layer of coveragePlans.querySelectorAll("[data-study-layer]")) {
        layer.toggleAttribute("hidden", layer.dataset.studyLayer !== mode);
      }
      for (const plan of coveragePlans.querySelectorAll(".atlas-coverage-canvas")) {
        const subject = mode === "parts" ? "part movement" : "human and machine coverage";
        plan.setAttribute("aria-label", plan.dataset.case + " Top View with " + subject);
      }
      atlas.querySelector("#coverage-overlap-key").hidden = mode === "parts" ||
        !coveragePlans.querySelector('[data-coverage-layer="overlap"]');
    }

    function studyPlan(row, plan, shared) {
      const card = renderPlan(row, plan, shared, null, {coverageOnly:true, switchable:true});
      const drawing = card.querySelector("svg");
      drawing.classList.add("atlas-coverage-canvas");
      drawing.dataset.case = row.case;
      for (const [mode, roles] of [["operators", ["human","machine"]], ["parts", ["part"]]]) {
        const pies = element("div", "atlas-coverage-pies");
        pies.dataset.studyLayer = mode;
        for (const role of roles) pies.append(coveragePie(row, role, roleNames[role]));
        card.append(pies);
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
      const pairKey = pair.map(row => row.case).join("-");
      if (pairKey !== lastPair) studyLayer = "operators";
      lastPair = pairKey;
      compareBars.classList.toggle("pair-study-bars", studyMode);
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
      let intervals = 4;
      if (studyMode) {
        findings.textContent = selectedRelation?.finding || (metricPair
          ? `${pair[0].case} recorded ${readableArea(pair[0], "activity_area_m2")} of activity and ${pair[1].case} recorded ${readableArea(pair[1], "activity_area_m2")}. Compare their A/F and role coverage below.`
          : "A/F is comparable across units. Each case uses its own area scale below.");
        const peak = Math.max(...pair.flatMap(row => [areaValue(row,"object_area_m2"), areaValue(row,"activity_area_m2")]));
        const step = peak <= 5 ? 1 : peak <= 10 ? 2 : peak <= 25 ? 5 : peak <= 50 ? 10 : 20;
        intervals = Math.max(1, Math.ceil(peak / step));
        extent = metricPair ? intervals * step : null;
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
      const planData = pair.map(row => {
        const plan = planFor(row);
        return studyMode ? {...plan, viewBox:areaPlanBox(plan)} : plan;
      });
      const common = atlas.querySelector("#atlas-common");
      const canShare = planData.every(plan => plan.metres);
      common.disabled = !canShare;
      common.closest("label").hidden = studyMode && !canShare;
      const shared = canShare && common.checked ? {
        width:Math.max(...planData.map(plan => plan.viewBox[2]*plan.metres)),
        height:Math.max(...planData.map(plan => plan.viewBox[3]*plan.metres))
      } : null;
      const layers = new Set(roleMode ? [selectedRole] : compareLayers.filter(input => input.checked).map(input => input.value));
      atlas.querySelector("#atlas-plan-note").textContent = "Original Top Views · " + (shared ? "Shared metre scale" : "Fitted separately");
      coveragePlans.replaceChildren();
      modelCards.replaceChildren();
      const metrics = pair.map(row => modelMetrics[row.case]);
      pair.forEach((row, index) => {
        const card = element("article", "atlas-card");
        const maximum = extent || (hasMetres(row) ? metricLimit : modelLimit(row));
        card.append(caseHeading(row, studyMode), bars(maximum, fieldsFor(row)), axis(maximum, extent ? axisUnit : unit(row), extent ? intervals : 4));
        compareBars.append(card);
        if (studyMode) {
          const ratios = element("p", "atlas-pair-ratio");
          ratios.append(element("span", "", "A/F  " + multiplier(row)),
            element("span", "atlas-inverse-ratio", "F/A  " + readableShare(shareOfActivity(row, "object_area_m2"))));
          card.append(ratios);
          const plan = planData[index];
          coveragePlans.append(studyPlan(row, plan, shared));
          modelCards.append(metricCard(row,metrics[index],plan));
        } else {
          plans.append(renderPlan(row, planData[index], shared, layers, {coverageOnly:true}));
        }
      });
      if (studyMode) {
        setStudyLayer(studyLayer);
        const key = pair.map(row => row.case).sort().join("-");
        const conclusion = conclusions[key] || pair.map(row =>
          `${row.case} records ${readableArea(row,"activity_area_m2")} of activity for a footprint of ${readableArea(row,"object_area_m2")}.`).join(" ");
        renderMemberPie(memberPie,pair,metrics);
        renderPairSummary(summary,pair,metrics,planData,conclusion);
      }
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
    for (const button of layerButtons) button.addEventListener("click", () => setStudyLayer(button.dataset.studyMode));
    atlas.querySelector(".atlas-layers").addEventListener("change", renderComparison);
    atlas.querySelector("#atlas-status").hidden = true;
    atlas.querySelector("#atlas-content").hidden = false;
    initializeSpatialRoles({
      rows, modes, median, caseUrl, areaValue, calibration,
      showPlan(row, role, selectTrack) {
        const plan = planFor(row);
        const track = selectTrack(plan.data.actions.filter(action => action.role === role), plan.viewBox);
        return {drawing: renderPlan(row, plan, null, new Set([role]), {highlighted:track}), track};
      },
      frameUrl: name => name ? new URL(name, casePage).href : null
    });
  }

  async function load() {
    const [response, registration, modelMetrics, outlines] = await Promise.all([
      fetch(casePage),
      fetch("case_area_comparison.csv").catch(() => null),
      fetch("case-model-metrics.json?v=2").then(result => result.ok ? result.json() : {}).catch(() => ({})),
      fetch("case-plan-outlines.json?v=1").then(result => result.ok ? result.json() : {}).catch(() => ({}))
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
    start(source.content, areaData, registered, modelMetrics, outlines);
  }

  load().catch(error => {
    console.error(error);
    for (const status of [atlas.querySelector("#atlas-status"), document.getElementById("roles-status")]) {
      status.textContent = "Could not load the case measurements. Reload the page to try again.";
    }
  });
})();

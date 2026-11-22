const groups = [
  { name: "Manual", color: "var(--site-orange)", cases: ["V01", "V06", "V07", "V20"] },
  { name: "Mixed", color: "var(--site-lime)", cases: ["V04", "V22", "V27", "V29"] },
  { name: "Robot", color: "var(--site-sky)", cases: ["V23", "V24", "V26", "V28", "V30"] }
];

const chooser = document.getElementById("case-groups");
const board = document.getElementById("board");
const statusMessage = document.getElementById("board-status");
const title = document.getElementById("board-title");
const meta = document.getElementById("board-meta");
const eventList = document.getElementById("event-list");
const previous = document.getElementById("previous-board");
const next = document.getElementById("next-board");
const pdf = document.getElementById("case-pdf");
const image = document.getElementById("board-image");
const imageLink = document.getElementById("board-image-link");
const caseLinks = new Map();

function hashFor(caseId, eventId) {
  return "#" + caseId + "/" + eventId;
}

function buildCasePicker(cases) {
  for (const group of groups) {
    const section = document.createElement("section");
    section.className = "case-group";
    section.style.setProperty("--group-color", group.color);
    const heading = document.createElement("h2");
    heading.textContent = group.name;
    const links = document.createElement("div");
    links.className = "case-list";
    for (const caseId of group.cases) {
      const entries = cases[caseId];
      const link = document.createElement("a");
      const count = document.createElement("small");
      link.className = "case-link";
      link.href = hashFor(caseId, entries[0].id);
      link.textContent = caseId;
      count.textContent = entries.length;
      link.setAttribute("aria-label", caseId + ", " + entries.length + " observations");
      link.append(count);
      links.append(link);
      caseLinks.set(caseId, { link, group: group.name });
    }
    section.append(heading, links);
    chooser.append(section);
  }
}

async function initialize() {
  const response = await fetch("boards/catalog.json");
  if (!response.ok) throw new Error("Could not load the observation catalog.");
  const { cases } = await response.json();
  buildCasePicker(cases);

  let currentCase;
  let eventIndex;
  function render() {
    const [requestedCase, requestedEvent] = location.hash.slice(1).split("/");
    const caseId = caseLinks.has(requestedCase) ? requestedCase : "V01";
    const entries = cases[caseId];
    const requestedIndex = entries.findIndex(entry => entry.id === requestedEvent);
    const index = Math.max(0, requestedIndex);
    const entry = entries[index];

    if (currentCase !== caseId) {
      caseLinks.get(currentCase)?.link.removeAttribute("aria-current");
      caseLinks.get(caseId).link.setAttribute("aria-current", "location");
      title.textContent = caseId + " · " + caseLinks.get(caseId).group;
      eventList.replaceChildren(...entries.map(item => new Option(item.id + " " + item.title, item.id)));
    }
    currentCase = caseId;
    eventIndex = index;
    eventList.value = entry.id;
    previous.disabled = index === 0;
    next.disabled = index === entries.length - 1;
    meta.textContent = (index + 1) + " of " + entries.length + " · " + entry.start + "–" + entry.end + " s";
    pdf.href = "boards/" + caseId + ".pdf#page=" + (index + 1);
    const source = "boards/" + caseId + "/" + entry.id + ".webp";
    imageLink.href = source;
    imageLink.setAttribute("aria-label", "Open full-size sheet for " + entry.id + " " + entry.title);
    image.width = entry.width;
    image.height = entry.height;
    image.alt = caseId + " " + entry.id + " " + entry.title + ", with three aligned masks and working directions";
    image.src = source;
    return requestedCase === caseId && requestedIndex !== -1;
  }

  function advance(delta) {
    const entry = cases[currentCase][eventIndex + delta];
    if (entry) location.hash = hashFor(currentCase, entry.id);
  }

  eventList.addEventListener("change", () => { location.hash = hashFor(currentCase, eventList.value); });
  previous.addEventListener("click", () => advance(-1));
  next.addEventListener("click", () => advance(1));
  window.addEventListener("hashchange", render);
  document.getElementById("opening-comparison")?.addEventListener("click", event => {
    if (event.target.closest("a") && event.button === 0 &&
        !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
      requestAnimationFrame(() => board.scrollIntoView());
    }
  });
  const openedFromBoardLink = render();
  statusMessage.hidden = true;
  board.hidden = false;
  if (openedFromBoardLink) board.scrollIntoView();
}

initialize().catch(error => {
  console.error(error);
  statusMessage.textContent = "The observations could not load. Refresh to try again.";
});

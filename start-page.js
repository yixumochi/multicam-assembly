(() => {
  const root = document.getElementById("path-page");
  if (!root) return;

  const gallery = root.querySelector(".case-gallery");
  const track = gallery.querySelector(".case-gallery-track");
  const dialog = gallery.querySelector(".case-gallery-dialog");
  const preview = dialog.querySelector(".case-preview-link");
  const previewImage = preview.querySelector("img");
  const controls = [...gallery.querySelectorAll("[data-gallery-direction]")];
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const simpleClick = event => event.button === 0 && !event.ctrlKey && !event.metaKey &&
    !event.shiftKey && !event.altKey && !event.defaultPrevented;

  function updateGalleryControls() {
    const end = track.scrollWidth - track.clientWidth;
    controls[0].disabled = track.scrollLeft < 2;
    controls[1].disabled = track.scrollLeft >= end - 2;
  }

  gallery.dataset.enhanced = "";
  track.addEventListener("scroll", updateGalleryControls, {passive:true});
  new ResizeObserver(updateGalleryControls).observe(track);
  for (const button of controls) {
    button.addEventListener("click", () => {
      const distance = Number(button.dataset.galleryDirection) * track.clientWidth * .82;
      track.scrollBy({left:distance, behavior:reducedMotion.matches ? "instant" : "smooth"});
    });
  }

  track.addEventListener("click", event => {
    const card = event.target.closest("[data-case-preview]");
    if (!card || !simpleClick(event) || typeof dialog.showModal !== "function") return;
    event.preventDefault();
    const {casePreview, galleryMode, fullImage} = card.dataset;
    dialog.querySelector("h2").textContent = casePreview + " · " + galleryMode;
    preview.href = card.href;
    preview.querySelector("span").textContent = "Open " + casePreview + " case sheet ↗";
    previewImage.alt = casePreview + " assembly video still";
    previewImage.src = fullImage;
    dialog.showModal();
  });
  dialog.querySelector(".case-preview-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
  preview.addEventListener("click", event => { if (simpleClick(event)) dialog.close(); });

  function showPanel(button) {
    const menu = button.closest(".start-module-menu");
    for (const choice of menu.querySelectorAll("[data-study-panel]")) {
      const panel = document.getElementById(choice.getAttribute("aria-controls"));
      const active = choice === button;
      choice.setAttribute("aria-pressed", String(active));
      panel.hidden = !active;
      if (!active) panel.querySelector("video")?.pause();
    }
  }

  for (const button of root.querySelectorAll("[data-study-panel]")) {
    button.addEventListener("click", () => showPanel(button));
  }

  function openWorkflowFromHash() {
    const panel = location.hash.slice(1);
    if (panel !== "v22-method" && panel !== "study-method") return;
    showPanel(root.querySelector(`[aria-controls="${panel}"]`));
    requestAnimationFrame(() => document.getElementById(panel).scrollIntoView({block:"start"}));
  }
  window.addEventListener("hashchange", openWorkflowFromHash);
  openWorkflowFromHash();

  root.addEventListener("click", event => {
    const link = event.target.closest("a");
    if (link?.hash && link.origin === location.origin && link.pathname === location.pathname &&
        link.hash === location.hash && simpleClick(event)) {
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    }
  });
})();

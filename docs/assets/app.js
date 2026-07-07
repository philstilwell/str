const copyButtons = document.querySelectorAll("[data-copy-target]");

function selectElementText(element) {
  const selection = window.getSelection();
  const range = document.createRange();
  range.selectNodeContents(element);
  selection.removeAllRanges();
  selection.addRange(range);
}

copyButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const target = document.querySelector(button.dataset.copyTarget);
    if (!target) return;
    const original = button.dataset.originalText || button.textContent;
    button.dataset.originalText = original;

    try {
      await navigator.clipboard.writeText(target.innerText.trim());
      button.textContent = "Copied";
      button.classList.add("copied");
      window.setTimeout(() => {
        button.textContent = original;
        button.classList.remove("copied");
      }, 1600);
    } catch {
      selectElementText(target);
      button.textContent = "Press Cmd+C";
      button.classList.add("manual-copy");
      window.setTimeout(() => {
        button.textContent = original;
        button.classList.remove("manual-copy");
      }, 3000);
    }
  });
});

const noteButtons = document.querySelectorAll(".note[aria-expanded]");

function closeNotes(except) {
  noteButtons.forEach((note) => {
    if (note === except) return;
    note.classList.remove("is-open");
    note.setAttribute("aria-expanded", "false");
  });
}

noteButtons.forEach((note) => {
  note.addEventListener("click", (event) => {
    event.stopPropagation();
    const willOpen = !note.classList.contains("is-open");
    closeNotes(note);
    note.classList.toggle("is-open", willOpen);
    note.setAttribute("aria-expanded", String(willOpen));
  });

  note.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    note.classList.remove("is-open");
    note.setAttribute("aria-expanded", "false");
    note.blur();
  });
});

document.addEventListener("click", () => closeNotes());

const toc = document.querySelector(".toc");
const tocToggle = document.querySelector(".toc-toggle");
const tocLinks = toc ? Array.from(toc.querySelectorAll('a[href^="#"]')) : [];
const tocTargets = tocLinks
  .map((link) => {
    const target = document.getElementById(decodeURIComponent(link.hash.slice(1)));
    return target ? { item: link.closest("li"), link, target } : null;
  })
  .filter(Boolean);
const mobileTocQuery = window.matchMedia("(max-width: 860px)");

function syncTocState() {
  if (!toc || !tocToggle) return;
  toc.classList.add("js-toc-ready");
  if (mobileTocQuery.matches) {
    toc.classList.remove("is-open");
    tocToggle.setAttribute("aria-expanded", "false");
    return;
  }
  toc.classList.add("is-open");
  tocToggle.setAttribute("aria-expanded", "true");
}

function setActiveTocItem(activeItem) {
  tocTargets.forEach((entry) => {
    const isActive = entry === activeItem;
    entry.link.classList.toggle("is-active", isActive);
    entry.item?.classList.toggle("is-active", isActive);
    if (isActive) {
      entry.link.setAttribute("aria-current", "location");
    } else {
      entry.link.removeAttribute("aria-current");
    }
  });
}

function syncActiveTocItem() {
  if (!tocTargets.length) return;

  const activationLine = Math.min(window.innerHeight * 0.3, 220);
  let activeItem = tocTargets[0];

  tocTargets.forEach((entry) => {
    if (entry.target.getBoundingClientRect().top <= activationLine) {
      activeItem = entry;
    }
  });

  setActiveTocItem(activeItem);
}

let activeTocFrame = 0;

function requestActiveTocSync() {
  if (activeTocFrame) return;
  activeTocFrame = window.requestAnimationFrame(() => {
    activeTocFrame = 0;
    syncActiveTocItem();
  });
}

if (toc && tocToggle) {
  syncTocState();
  syncActiveTocItem();
  mobileTocQuery.addEventListener("change", syncTocState);
  window.addEventListener("scroll", requestActiveTocSync, { passive: true });
  window.addEventListener("resize", requestActiveTocSync);
  window.addEventListener("hashchange", () => window.setTimeout(syncActiveTocItem, 80));

  tocToggle.addEventListener("click", () => {
    const isOpen = toc.classList.toggle("is-open");
    tocToggle.setAttribute("aria-expanded", String(isOpen));
  });

  tocLinks.forEach((link) => {
    link.addEventListener("click", () => {
      const clickedItem = tocTargets.find((entry) => entry.link === link);
      if (clickedItem) setActiveTocItem(clickedItem);
      if (!mobileTocQuery.matches) return;
      toc.classList.remove("is-open");
      tocToggle.setAttribute("aria-expanded", "false");
    });
  });
}

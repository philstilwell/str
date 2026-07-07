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

if (toc && tocToggle) {
  syncTocState();
  mobileTocQuery.addEventListener("change", syncTocState);

  tocToggle.addEventListener("click", () => {
    const isOpen = toc.classList.toggle("is-open");
    tocToggle.setAttribute("aria-expanded", String(isOpen));
  });

  toc.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      if (!mobileTocQuery.matches) return;
      toc.classList.remove("is-open");
      tocToggle.setAttribute("aria-expanded", "false");
    });
  });
}

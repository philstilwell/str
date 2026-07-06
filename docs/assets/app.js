const copyButtons = document.querySelectorAll("[data-copy-target]");

copyButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const target = document.querySelector(button.dataset.copyTarget);
    if (!target) return;

    try {
      await navigator.clipboard.writeText(target.innerText.trim());
      const original = button.textContent;
      button.textContent = "Copied";
      button.classList.add("copied");
      window.setTimeout(() => {
        button.textContent = original;
        button.classList.remove("copied");
      }, 1600);
    } catch {
      button.textContent = "Select prompt";
    }
  });
});


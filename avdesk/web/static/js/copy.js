// Copy buttons replace outbound Slack/e-mail integrations (deliberately not built).
document.querySelectorAll("[data-copy]").forEach(function (button) {
  button.addEventListener("click", function () {
    navigator.clipboard.writeText(button.dataset.copy).then(function () {
      const original = button.textContent;
      button.textContent = "Copiado!";
      setTimeout(function () { button.textContent = original; }, 1500);
    });
  });
});

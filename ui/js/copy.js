// Copy buttons replace outbound Slack/e-mail integrations (deliberately not built, ADR-5).
import { h } from "./page.js";

export function copyButton(label, text, className = "button-secondary") {
  const button = h("button", { type: "button", class: className }, label);
  button.addEventListener("click", () => {
    navigator.clipboard.writeText(text).then(() => {
      button.textContent = "Copiado!";
      setTimeout(() => { button.textContent = label; }, 1500);
    });
  });
  return button;
}

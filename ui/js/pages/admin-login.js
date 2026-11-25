import { ApiError, adminSession, requestsApi } from "../api.js";
import { h, link, queryParam, runPage, waitingOptions } from "../page.js";

function nextPage() {
  const target = queryParam("next") || "";
  // Only pages of this site, so the login cannot be used to bounce people elsewhere.
  return target.startsWith("/") && !target.startsWith("//") ? target : link("admin/index.html");
}

runPage("Entrar", async () => {
  const error = h("span", { class: "error", hidden: true });
  const password = h("input", { id: "password", name: "password", type: "password", autocomplete: "current-password", autofocus: true });
  const form = h("form", {},
    h("div", { class: "field" }, h("label", { for: "password" }, "Senha"), password, error),
    h("button", { type: "submit" }, "Entrar"));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.hidden = true;
    try {
      const session = await requestsApi.post("/admin/session", { password: password.value }, waitingOptions);
      adminSession.start(session.token);
      location.href = nextPage();
    } catch (failure) {
      error.textContent = failure instanceof ApiError && failure.status === 401 ? "Senha incorreta." : failure.message;
      error.hidden = false;
    }
  });
  return h("section", { class: "card" }, h("h1", {}, "Área da gerência de Audiovisual"), form);
});

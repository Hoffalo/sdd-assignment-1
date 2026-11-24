import { ApiError, requestsApi } from "../api.js";
import { briefingForm } from "../briefing-form.js";
import { fill, flash, formatDate, formatDateTime, fragmentParam, h, runPage, statusBadge, waitingOptions } from "../page.js";

const token = fragmentParam("t");
const tokenPath = `/requests/by-token/${encodeURIComponent(token || "")}`;

function timeline(events) {
  return h("ol", { class: "timeline" }, events.map((e) => h("li", {},
    h("time", {}, formatDateTime(e.created_at)), ` · ${e.to_status_label}`, e.note ? [h("br"), e.note] : null)));
}

function reviewCard(tracked) {
  if (tracked.status !== "in_review" || !tracked.review_url) return null;
  return h("section", { class: "card review" }, h("h2", {}, "Sua vez de revisar"),
    h("p", {}, "Uma nova versão do vídeo está pronta. Assista e deixe seus comentários direto no Frame.io, no ponto exato do vídeo."),
    h("p", {}, h("a", { class: "button", href: tracked.review_url, target: "_blank", rel: "noopener" }, "Assistir e comentar no Frame.io")),
    h("p", { class: "help" }, "O Frame.io abre em uma nova aba. Ele não permite ser exibido dentro de outros sites, por isso o link."));
}

function render(tracked, catalog, edited = null, errors = {}) {
  const analyst = catalog.analysts.find((a) => a.id === tracked.analyst_id);
  const parts = [
    h("p", { class: "help" }, tracked.public_code),
    h("h1", {}, tracked.briefing.title),
    h("p", {}, statusBadge(tracked.status, tracked.status_label), " ",
      tracked.rush ? h("span", { class: "badge badge-rush" }, "Prazo curto") : null),
    h("section", { class: "card" },
      h("p", {}, h("strong", {}, "Prazo pedido: "), formatDate(tracked.briefing.needed_by)),
      analyst ? h("p", {}, h("strong", {}, "Responsável: "), analyst.name) : null,
      tracked.delivery_url ? h("p", {}, h("strong", {}, "Entrega: "),
        h("a", { href: tracked.delivery_url, rel: "noopener" }, "abrir o vídeo final")) : null,
      h("p", { class: "help" }, "Guarde o link desta página: só quem tem o link consegue ver o pedido.")),
    reviewCard(tracked),
    h("h2", {}, "Histórico"),
    timeline(tracked.timeline),
  ];
  if (tracked.editable) {
    parts.push(h("h2", {}, "Complete o briefing"),
      h("p", { class: "notice" }, "A gerência de Audiovisual precisa de mais informações. Atualize o briefing abaixo e envie de novo."),
      briefingForm({ catalog, briefing: edited || tracked.briefing, errors, submitLabel: "Reenviar briefing",
        onSubmit: (briefing) => resubmit(briefing, catalog) }));
  }
  return parts;
}

async function resubmit(briefing, catalog) {
  const main = document.querySelector("main");
  try {
    const updated = await requestsApi.put(`${tokenPath}/briefing`, briefing, waitingOptions);
    fill(main, render(updated, catalog));
    flash("Briefing atualizado e reenviado. Obrigado!");
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      const current = await requestsApi.get(tokenPath, waitingOptions);
      fill(main, render(current, catalog, briefing, error.body.errors));
    } else {
      flash(error.message, "error");
    }
  }
  window.scrollTo(0, 0);
}

runPage("Acompanhar pedido", async () => {
  if (!token) throw new ApiError(404, {});
  const [tracked, catalog] = await Promise.all([requestsApi.get(tokenPath, waitingOptions),
                                                requestsApi.get("/catalog", waitingOptions)]);
  document.title = `${tracked.public_code} · Audiovisual BRASA`;
  const parts = render(tracked, catalog);
  const message = sessionStorage.getItem("avdesk-flash");
  if (message) {
    sessionStorage.removeItem("avdesk-flash");
    parts.unshift(h("p", { class: "flash", role: "status" }, message));
  }
  return parts;
});

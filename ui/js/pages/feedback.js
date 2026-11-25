import { ApiError, feedbackApi } from "../api.js";
import { fill, fragmentParam, h, runPage, waitingOptions } from "../page.js";

const token = fragmentParam("t");
const invitePath = `/invites/${encodeURIComponent(token || "")}`;

// Every closed state is a friendly page: a stale link is a normal situation
// for a reviewer, not an error.
const CLOSED_MESSAGES = {
  used: "Este link já foi usado. Obrigado pela sua avaliação!",
  expired: "Este link expirou. Se ainda quiser avaliar, fale com a gerência de Audiovisual.",
  not_found: "Não encontramos este link de avaliação. Confira se ele foi copiado inteiro.",
};

function message(heading, text) {
  return h("section", { class: "card" }, h("h1", {}, heading), h("p", {}, text));
}

function radios(name, options, chosen) {
  return h("div", { class: "options" }, options.map(([value, label]) =>
    h("label", {}, h("input", { type: "radio", name, value, checked: String(chosen ?? "") === String(value) }), " ", label)));
}

function feedbackForm(view, answers = {}, errors = {}) {
  const field = (key, ...children) => h("div", { class: `field${errors[key] ? " has-error" : ""}` }, ...children,
    errors[key] ? h("span", { class: "error" }, errors[key]) : null);
  const form = h("form", { class: "card" },
    view.dimensions.map((d) => field(d.key, h("span", { class: "label required" }, d.label),
      radios(d.key, [1, 2, 3, 4, 5].map((n) => [n, n]), answers[d.key]))),
    field("outcome", h("span", { class: "label required" }, "O vídeo está pronto para uso?"),
      radios("outcome", view.outcomes.map((o) => [o.value, o.label]), answers.outcome)),
    field("comment", h("label", { for: "comment" }, "Comentários"), h("textarea", { id: "comment", name: "comment" }, answers.comment || "")),
    h("button", { type: "submit" }, "Enviar avaliação"));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    const main = document.querySelector("main");
    try {
      await feedbackApi.post(`${invitePath}/response`, data, waitingOptions);
      fill(main, message("Obrigado!", "Avaliação enviada. Muito obrigado!"));
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        fill(main, page(view, data, error.body.errors));
      } else if (error instanceof ApiError && error.body.state) {
        fill(main, message("Link indisponível", CLOSED_MESSAGES[error.body.state]));
      } else {
        throw error;
      }
    }
  });
  return form;
}

function page(view, answers, errors) {
  const invite = view.invite;
  return [
    h("p", { class: "help" }, `${invite.public_code} · ${invite.type_label}`),
    h("h1", {}, `Como foi o vídeo “${invite.title}”?`),
    h("p", {}, `Oi, ${invite.recipient_label}! Sua avaliação ajuda a gerência de Audiovisual a melhorar a cada entrega. `,
      h("a", { href: invite.delivery_url, rel: "noopener" }, "Rever o vídeo entregue"), "."),
    feedbackForm(view, answers, errors),
  ];
}

runPage("Avaliação", async () => {
  let view;
  try {
    view = await feedbackApi.get(invitePath, waitingOptions);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return message("Link indisponível", CLOSED_MESSAGES.not_found);
    throw error;
  }
  if (view.state !== "open") return message("Link indisponível", CLOSED_MESSAGES[view.state]);
  return page(view, {}, {});
});

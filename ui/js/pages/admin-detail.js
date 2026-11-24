import { ApiError, feedbackApi, requestsApi } from "../api.js";
import { copyButton } from "../copy.js";
import { fill, flash, formatDate, formatDateTime, h, link, queryParam, requireAdmin, runPage, statusBadge, waitingOptions } from "../page.js";

const requestId = Number(queryParam("id"));
const adminCall = { ...waitingOptions, admin: true };
// Buttons that need no input; every other action opens a small form first.
const ONE_CLICK = new Set(["start_production", "close"]);
const DANGEROUS = new Set(["decline", "cancel"]);

function actionFields(name, catalog, workload) {
  const textarea = (label, help) => h("div", { class: "field" },
    h("label", { for: `note-${name}`, class: "required" }, label), h("span", { class: "help" }, help),
    h("textarea", { id: `note-${name}`, name: "note" }));
  switch (name) {
    case "accept": return h("div", { class: "field" }, h("label", { for: "analyst_id", class: "required" }, "Quem produz"),
      h("select", { id: "analyst_id", name: "analyst_id" }, h("option", { value: "" }, "Escolha…"),
        workload.analysts.map((a) => h("option", { value: a.id },
          `${a.name} (${a.open} em aberto${a.open >= workload.threshold ? ", carga alta" : ""})`))));
    case "request_info": return textarea("O que falta no briefing?", "Quem pediu verá esta mensagem e poderá completar o briefing.");
    case "decline": return textarea("Por que o pedido foi recusado?", "Quem pediu verá esta mensagem.");
    case "send_to_review": return h("div", { class: "field" }, h("label", { for: "review_url", class: "required" }, "Link de revisão do Frame.io"),
      h("span", { class: "help" }, "Aparece na página de acompanhamento de quem pediu."),
      h("input", { id: "review_url", name: "review_url", type: "url", placeholder: "https://f.io/…" }));
    case "deliver": return h("div", { class: "field" }, h("label", { for: "delivery_url", class: "required" }, "Link do Drive com o arquivo final"),
      h("input", { id: "delivery_url", name: "delivery_url", type: "url" }));
    default: return h("div", { class: "field" }, h("label", { for: `note-${name}` }, "Observação (opcional)"),
      h("input", { id: `note-${name}`, name: "note" }));
  }
}

async function send(path, body) {
  try {
    const updated = await requestsApi.post(path, body, adminCall);
    await rerender(updated, "Status atualizado.");
  } catch (error) {
    if (!(error instanceof ApiError) || ![409, 422].includes(error.status)) throw error;
    flash(error.message, "error");
    window.scrollTo(0, 0);
  }
}

function actionForm(action, catalog, workload) {
  const form = h("form", {}, ONE_CLICK.has(action.name) ? null : actionFields(action.name, catalog, workload),
    h("button", { type: "submit", class: DANGEROUS.has(action.name) ? "button-danger" : null },
      ONE_CLICK.has(action.name) ? action.label : "Confirmar"));
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    send(`/admin/requests/${requestId}/actions`, { action: action.name, ...Object.fromEntries(new FormData(form)) });
  });
  return ONE_CLICK.has(action.name) ? form : h("details", { class: "action" }, h("summary", {}, action.label), form);
}

// The feedback service owns the invites; if it is down, only this section
// says so and the rest of the page keeps working.
function invitesSection(invites, detail) {
  if (invites === null) {
    return h("p", { class: "notice notice-error" }, "As avaliações estão indisponíveis no momento (serviço de avaliação fora do ar). Tente de novo mais tarde.");
  }
  if (!invites.length) return null;
  return [h("h3", {}, "Links de avaliação"), h("ul", {}, invites.map((invite) => {
    const url = `${link("avaliacao.html")}#t=${encodeURIComponent(invite.token)}`;
    const mail = `mailto:${detail.briefing.requester_email}?subject=${encodeURIComponent(`Avalie o vídeo ${detail.public_code}`)}` +
      `&body=${encodeURIComponent(`Oi! O vídeo ficou pronto. Conta pra gente como foi: ${url}`)}`;
    return h("li", {}, `${invite.recipient_label}${invite.is_requester ? " (quem pediu)" : ""} · `,
      invite.used_at ? "respondido" : `expira em ${formatDateTime(invite.expires_at)}`, " · ",
      copyButton("copiar link", url, "button-link"),
      invite.is_requester ? [" · ", h("a", { href: mail }, "enviar por e-mail")] : null);
  }))];
}

function answersList(detail, catalog) {
  const questions = catalog.questions.filter((q) => q.type_code === null || q.type_code === detail.briefing.type_code);
  return h("dl", {}, questions.flatMap((q) => {
    const value = detail.briefing.answers[q.key];
    if (!value || (Array.isArray(value) && !value.length)) return [];
    const shown = Array.isArray(value) ? value.join(", ") : ({ sim: "Sim", nao: "Não" }[value] || value);
    return [h("dt", {}, h("strong", {}, q.label)), h("dd", {}, shown)];
  }));
}

function render(detail, catalog, workload, invites) {
  const briefing = detail.briefing;
  const type = catalog.types.find((t) => t.code === briefing.type_code) || { label: briefing.type_code };
  const diretoria = catalog.diretorias.find((d) => d.id === briefing.diretoria_id) || { name: "—" };
  const analyst = catalog.analysts.find((a) => a.id === detail.analyst_id);
  const trackingUrl = `${link("pedido.html")}#t=${encodeURIComponent(detail.tracking_token)}`;
  const undo = h("button", { type: "button", class: "button-secondary" }, "Desfazer última mudança");
  undo.addEventListener("click", () => send(`/admin/requests/${requestId}/undo`));

  return [
    h("p", { class: "help" }, h("a", { href: link("admin/index.html") }, "← Pedidos"), ` · ${detail.public_code}`),
    h("h1", {}, briefing.title),
    h("p", {}, statusBadge(detail.status, detail.status_label), " ",
      detail.rush ? h("span", { class: "badge badge-rush" }, "Prazo curto") : null, " ",
      h("span", { class: "badge" }, `Briefing ${detail.briefing_score}%`), " ",
      detail.task_url ? h("a", { href: detail.task_url, rel: "noopener" }, "Tarefa no ClickUp") : null),
    h("section", { class: "card" }, h("h3", {}, "Ações"),
      h("p", { class: "help" }, "Ações que precisam de informação abrem um formulário ao clicar."),
      h("div", { class: "actions" }, detail.actions.length
        ? detail.actions.map((a) => actionForm(a, catalog, workload))
        : h("p", {}, "Nenhuma ação disponível: o pedido está encerrado.")),
      detail.can_undo ? undo : null),
    h("section", { class: "card" }, h("h3", {}, "Comunicação"),
      h("p", {}, "Link de acompanhamento para quem pediu: ", h("a", { href: trackingUrl }, trackingUrl)),
      h("p", {}, copyButton("Copiar mensagem para o Slack", detail.slack_message)),
      invitesSection(invites, detail)),
    h("section", { class: "card" }, h("h3", {}, "Briefing"),
      h("details", {}, h("summary", {}, "Ver como Markdown"), h("pre", { class: "copyable" }, detail.briefing_markdown),
        copyButton("Copiar Markdown", detail.briefing_markdown)),
      h("p", {}, h("strong", {}, "Solicitante: "), `${briefing.requester_name} <${briefing.requester_email}> · ${diretoria.name}`),
      h("p", {}, h("strong", {}, "Tipo: "), type.label, briefing.type_detail ? ` (${briefing.type_detail})` : "",
        briefing.needs_c_level_approval ? " · precisa de aprovação C-Level" : ""),
      h("p", {}, h("strong", {}, "Campanha: "), briefing.campaign || "—"),
      h("p", {}, h("strong", {}, "Prazo: "), `${formatDate(briefing.needed_by)} · ${briefing.needed_by_reason}`),
      detail.rush ? h("p", { class: "notice notice-rush" }, h("strong", {}, "Prazo curto: "), briefing.rush_reason) : null,
      analyst ? h("p", {}, h("strong", {}, "Responsável: "), analyst.name) : null,
      detail.review_url ? h("p", {}, h("strong", {}, "Revisão (Frame.io): "),
        h("a", { href: detail.review_url, target: "_blank", rel: "noopener" }, detail.review_url)) : null,
      detail.delivery_url ? h("p", {}, h("strong", {}, "Entrega: "), h("a", { href: detail.delivery_url, rel: "noopener" }, detail.delivery_url)) : null,
      answersList(detail, catalog)),
    h("h2", {}, "Histórico"),
    h("ol", { class: "timeline" }, detail.timeline.map((e) => h("li", {},
      h("time", {}, formatDateTime(e.created_at)), ` · ${e.to_status_label} · ${e.actor}`, e.note ? [h("br"), e.note] : null))),
  ];
}

let cached = {};

async function loadInvites() {
  try {
    return await feedbackApi.get(`/admin/requests/${requestId}/invites`, { admin: true });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    return null;
  }
}

async function rerender(detail, message) {
  const [workload, invites] = await Promise.all([requestsApi.get("/admin/workload", adminCall), loadInvites()]);
  fill(document.querySelector("main"), render(detail, cached.catalog, workload, invites));
  if (message) flash(message);
  window.scrollTo(0, 0);
}

if (requireAdmin()) {
  runPage("Pedido", async () => {
    const [catalog, detail, workload, invites] = await Promise.all([
      requestsApi.get("/catalog", waitingOptions), requestsApi.get(`/admin/requests/${requestId}`, adminCall),
      requestsApi.get("/admin/workload", adminCall), loadInvites()]);
    cached = { catalog };
    document.title = `${detail.public_code} · Audiovisual BRASA`;
    return render(detail, catalog, workload, invites);
  });
}

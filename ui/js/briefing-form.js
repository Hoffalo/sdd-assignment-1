// The briefing form, built from the catalog the requests service publishes,
// so a new question or type in seed.json needs no UI change.
// The live score and deadline notice are previews only: the service's
// BriefingValidator and BriefingScorer decide on submit.

import { requestsApi } from "./api.js";
import { formatDate, h } from "./page.js";

const ANSWER_PREFIX = "q_";

function fieldError(errors, key) {
  return errors[key] ? h("span", { class: "error", id: `${key}-error` }, errors[key]) : null;
}

function field(key, errors, ...children) {
  return h("div", { class: `field${errors[key] ? " has-error" : ""}` }, ...children, fieldError(errors, key));
}

function textField(name, label, value, errors, { type = "text", required = true, help = "" } = {}) {
  const input = type === "textarea"
    ? h("textarea", { id: name, name }, value || "")
    : h("input", { id: name, name, type, value: value || "" });
  return field(name, errors, h("label", { for: name, class: required ? "required" : null }, label),
    help ? h("span", { class: "help" }, help) : null, input);
}

function choice(options, value) {
  return [h("option", { value: "" }, "Escolha…"),
    ...options.map((o) => h("option", { value: o.value, selected: String(o.value) === String(value ?? "") }, o.label))];
}

function questionInput(question, value) {
  const name = ANSWER_PREFIX + question.key;
  switch (question.kind) {
    case "textarea": return h("textarea", { id: name, name }, value || "");
    case "choice": return h("select", { id: name, name }, choice(question.options.map((o) => ({ value: o, label: o })), value));
    case "multichoice": return h("div", { class: "options" }, question.options.map((o) =>
      h("label", {}, h("input", { type: "checkbox", name, value: o, checked: (value || []).includes(o) }), " ", o)));
    case "yesno": return h("div", { class: "options" }, [["sim", "Sim"], ["nao", "Não"]].map(([v, label]) =>
      h("label", {}, h("input", { type: "radio", name, value: v, checked: value === v }), " ", label)));
    default: return h("input", { id: name, name, value: value || "", type: { url: "url", date: "date" }[question.kind] || "text" });
  }
}

function questionBlock(question, answers, errors) {
  const name = ANSWER_PREFIX + question.key;
  const grouped = question.kind === "multichoice" || question.kind === "yesno";
  const label = grouped
    ? h("span", { class: `label${question.required ? " required" : ""}` }, question.label)
    : h("label", { for: name, class: question.required ? "required" : null }, question.label);
  const block = field(question.key, errors, label, question.help ? h("span", { class: "help" }, question.help) : null,
    questionInput(question, answers[question.key]));
  block.dataset.question = question.key;
  if (question.depends_on) {
    block.dataset.dependsOn = ANSWER_PREFIX + question.depends_on;
    block.dataset.dependsValue = question.depends_value;
  }
  return block;
}

// Common sections first, then one block per type, in seed order.
function questionSections(catalog) {
  const sections = [];
  for (const typeCode of [null, ...catalog.types.map((t) => t.code)]) {
    const byTitle = new Map();
    for (const q of catalog.questions.filter((q) => q.type_code === typeCode)) {
      if (!byTitle.has(q.section)) byTitle.set(q.section, []);
      byTitle.get(q.section).push(q);
    }
    for (const [title, questions] of byTitle) sections.push({ typeCode, title, questions });
  }
  return sections;
}

function readBriefing(form, catalog) {
  const data = new FormData(form);
  const answers = {};
  for (const q of catalog.questions) {
    const name = ANSWER_PREFIX + q.key;
    answers[q.key] = q.kind === "multichoice" ? data.getAll(name) : (data.get(name) || "").trim();
  }
  return {
    requester_name: data.get("requester_name") || "", requester_email: data.get("requester_email") || "",
    diretoria_id: data.get("diretoria_id") || null, type_code: data.get("type_code") || "",
    type_detail: data.get("type_detail") || "", title: data.get("title") || "", campaign: data.get("campaign") || "",
    needs_c_level_approval: data.get("needs_c_level_approval") === "sim",
    needed_by: data.get("needed_by") || "", needed_by_reason: data.get("needed_by_reason") || "",
    rush_reason: data.get("rush_reason") || "", answers,
  };
}

function wireLiveBehaviour(form) {
  const detailField = form.querySelector("#type-detail-field");
  const detailLabel = form.querySelector("#type-detail-label");
  const notice = form.querySelector("#deadline-notice");
  const rushReason = form.querySelector("#rush-reason-field");
  const selectedType = () => form.querySelector("input[name=type_code]:checked");

  function updateTypeDetail() {
    const type = selectedType();
    const label = type ? type.dataset.detailLabel : "";
    detailField.hidden = !label;
    if (label) detailLabel.textContent = label;
    form.querySelectorAll("fieldset[data-type]").forEach((section) => {
      section.hidden = section.dataset.type !== "" && section.dataset.type !== (type ? type.value : null);
    });
  }

  function triggerMatches(fieldName, expected) {
    return Array.from(form.querySelectorAll(`[name="${fieldName}"]`)).some((input) =>
      (input.type === "checkbox" || input.type === "radio") ? input.checked && input.value === expected : input.value === expected);
  }

  // Mirrors Question.is_shown in the service, which stays the authority on submit.
  function updateFollowUps() {
    form.querySelectorAll("[data-depends-on]").forEach((block) => {
      block.hidden = !triggerMatches(block.dataset.dependsOn, block.dataset.dependsValue);
    });
  }

  function isAnswered(block) {
    return Array.from(block.querySelectorAll("input, select, textarea")).some((input) =>
      (input.type === "checkbox" || input.type === "radio") ? input.checked : input.value.trim() !== "");
  }

  function updateScore() {
    const visible = Array.from(form.querySelectorAll("[data-question]"))
      .filter((block) => !block.hidden && !block.closest("fieldset").hidden);
    const score = visible.length ? Math.round((100 * visible.filter(isAnswered).length) / visible.length) : 0;
    form.querySelector("#score-value").textContent = `${score}%`;
    form.querySelector("#score-bar").style.width = `${score}%`;
  }

  async function updateDeadline() {
    const type = selectedType();
    const neededBy = form.querySelector("[name=needed_by]").value;
    if (!type || !neededBy) { notice.hidden = true; rushReason.hidden = true; return; }
    const params = new URLSearchParams({ type_code: type.value, needed_by: neededBy,
      needs_c_level_approval: String(form.querySelector("[name=needs_c_level_approval]").checked) });
    try {
      const result = await requestsApi.get(`/deadline?${params}`);
      rushReason.hidden = !result.rush;
      notice.hidden = false;
      notice.classList.toggle("notice-rush", result.rush);
      notice.textContent = result.rush
        ? `Prazo curto: esse tipo de vídeo pede ${result.required_days} dias e você deu ${result.available_days}. ` +
          `A data mais realista é ${formatDate(result.earliest_date)}. Você ainda pode enviar, explicando abaixo por que a data não pode mudar.`
        : `Prazo ok: ${result.available_days} dias até a entrega.`;
    } catch (error) {
      // If the check fails, keep the reason box visible: the service still decides.
      notice.hidden = true;
      rushReason.hidden = false;
    }
  }

  form.addEventListener("change", (event) => {
    if (["type_code", "needed_by", "needs_c_level_approval"].includes(event.target.name)) {
      updateTypeDetail();
      updateDeadline();
    }
    updateFollowUps();
    updateScore();
  });
  form.addEventListener("input", updateScore);
  updateTypeDetail();
  updateFollowUps();
  updateDeadline();
  updateScore();
}

export function briefingForm({ catalog, briefing = {}, errors = {}, submitLabel, onSubmit }) {
  const answers = briefing.answers || {};
  const form = h("form", { id: "briefing-form", novalidate: true },
    h("div", { class: "sticky-score", "aria-live": "polite" },
      h("span", {}, "Briefing completo: ", h("strong", { id: "score-value" }, "—")),
      h("div", { class: "meter" }, h("span", { id: "score-bar", style: "width: 0" }))),
    Object.keys(errors).length
      ? h("p", { class: "notice notice-error" }, "Faltam algumas informações. Os campos marcados abaixo precisam de atenção.")
      : null,
    h("fieldset", {}, h("legend", {}, "Quem está pedindo"),
      textField("requester_name", "Seu nome", briefing.requester_name, errors),
      textField("requester_email", "Seu e-mail @gobrasa.org", briefing.requester_email, errors, { type: "email" }),
      field("diretoria_id", errors, h("label", { for: "diretoria_id", class: "required" }, "Sua diretoria"),
        h("select", { id: "diretoria_id", name: "diretoria_id" },
          choice(catalog.diretorias.map((d) => ({ value: d.id, label: d.name })), briefing.diretoria_id)))),
    h("fieldset", {}, h("legend", {}, "O vídeo"),
      field("type_code", errors, h("span", { class: "label required" }, "Que tipo de vídeo?"),
        h("div", { class: "options" }, catalog.types.map((t) => h("label", {},
          h("input", { type: "radio", name: "type_code", value: t.code, dataset: { detailLabel: t.detail_label || "" },
                       checked: t.code === briefing.type_code }), " ", t.label)))),
      (() => {
        const detail = field("type_detail", errors,
          h("label", { for: "type_detail", class: "required", id: "type-detail-label" }, "Conte mais sobre o tipo"),
          h("input", { id: "type_detail", name: "type_detail", value: briefing.type_detail || "" }));
        detail.id = "type-detail-field";
        return detail;
      })(),
      textField("title", "Título do pedido", briefing.title, errors, { help: "Um nome curto para todo mundo saber de qual vídeo estamos falando." }),
      textField("campaign", "Campanha", briefing.campaign, errors, { required: false, help: "A qual campanha, conferência ou produto da BRASA o vídeo pertence?" }),
      h("div", { class: "field" }, h("label", {},
        h("input", { type: "checkbox", name: "needs_c_level_approval", value: "sim", checked: Boolean(briefing.needs_c_level_approval) }),
        " Precisa de aprovação C-Level"))),
    h("fieldset", {}, h("legend", {}, "Prazo"),
      textField("needed_by", "Para quando você precisa do vídeo pronto?", briefing.needed_by, errors, { type: "date" }),
      textField("needed_by_reason", "Por que essa data?", briefing.needed_by_reason, errors, { help: "Ex.: abertura das inscrições, dia da conferência." }),
      h("div", { id: "deadline-notice", class: "notice", hidden: true }),
      h("div", { id: "rush-reason-field" },
        textField("rush_reason", "O prazo é curto. Por que ele não pode mudar?", briefing.rush_reason, errors, { type: "textarea" }))),
    questionSections(catalog).map((section) => h("fieldset", { dataset: { type: section.typeCode || "" } },
      h("legend", {}, section.title), section.questions.map((q) => questionBlock(q, answers, errors)))),
    h("button", { type: "submit" }, submitLabel));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      await onSubmit(readBriefing(form, catalog));
    } finally {
      button.disabled = false;
    }
  });
  wireLiveBehaviour(form);
  return form;
}

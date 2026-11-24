// Page skeleton and small DOM helpers shared by every page.
// Text always goes in through textContent (h() never sets innerHTML), so
// data typed by requesters cannot inject markup into the AV manager's pages.

import { ApiError, ServiceStarting, adminSession } from "./api.js";

export const ROOT = new URL("../", import.meta.url);

export function link(path) { return new URL(path, ROOT).href; }

function nodes(content) {
  return [content].flat(Infinity).filter((part) => part !== null && part !== undefined && part !== false);
}

// Replaces what a container shows; empty parts (a section a page left out) are skipped.
export function fill(container, content) { container.replaceChildren(...nodes(content)); }

export function h(tag, attributes = {}, ...children) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (value === false || value === null || value === undefined) continue;
    if (name.startsWith("on")) element.addEventListener(name.slice(2), value);
    else if (name === "dataset") Object.assign(element.dataset, value);
    else element.setAttribute(name, value === true ? "" : value);
  }
  for (const child of nodes(children)) {
    element.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return element;
}

const DATE = new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" });
const DATE_TIME = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });

// Dates (YYYY-MM-DD) are calendar days, so they are shown in UTC to avoid
// slipping a day; timestamps are instants, shown in the reader's zone.
export function formatDate(iso) { return iso ? DATE.format(new Date(iso.slice(0, 10) + "T00:00:00Z")) : "—"; }
export function formatDateTime(iso) { return iso ? DATE_TIME.format(new Date(iso)) : "—"; }
export function percent(value) { return value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`; }
export function number(value) { return value === null || value === undefined ? "—" : value.toFixed(1); }

export function statusBadge(status, label) { return h("span", { class: `badge badge-${status}` }, label); }

export function fragmentParam(name) { return new URLSearchParams(location.hash.slice(1)).get(name); }
export function queryParam(name) { return new URLSearchParams(location.search).get(name); }

function topbar() {
  const nav = adminSession.isActive()
    ? [h("a", { href: link("admin/index.html") }, "Pedidos"), h("a", { href: link("admin/metricas.html") }, "Métricas"),
       h("button", { type: "button", class: "button-link", onclick: () => { adminSession.end(); location.href = link("index.html"); } }, "Sair")]
    : [h("a", { href: link("pedido-novo.html") }, "Novo pedido"), h("a", { href: link("admin/entrar.html") }, "Gerência")];
  return h("header", { class: "topbar" },
    h("a", { class: "brand", href: link("index.html") }, h("span", {}, "BRASA"), " AV Desk"),
    h("nav", {}, nav));
}

export function flash(message, kind = "") {
  const main = document.querySelector("main");
  const note = h("p", { class: `flash${kind ? " flash-" + kind : ""}`, role: "status" }, message);
  main.prepend(note);
  return note;
}

function startingNotice() {
  if (!document.getElementById("starting-notice")) {
    const note = flash("O AV Desk estava em pausa e está acordando. Isso pode levar até um minuto…");
    note.id = "starting-notice";
  }
}

export const waitingOptions = { onStarting: startingNotice };

function failureCard(error, retry) {
  if (error instanceof ServiceStarting) {
    return h("section", { class: "card" },
      h("h1", {}, "O AV Desk ainda está iniciando"),
      h("p", {}, "O serviço fica em pausa quando ninguém usa e leva até um minuto para acordar. Tente de novo em instantes."),
      h("button", { type: "button", onclick: retry }, "Tentar de novo"));
  }
  if (error instanceof ApiError && error.status === 401) {
    requireAdmin();
    return h("p", { class: "help" }, "Sessão expirada. Abrindo a página de login…");
  }
  if (error instanceof ApiError && error.status === 404) {
    return h("section", { class: "card" }, h("h1", {}, "Não encontramos esta página"),
      h("p", {}, "Confira se o link foi copiado inteiro."), h("p", {}, h("a", { href: link("index.html") }, "Voltar para o início")));
  }
  return h("section", { class: "card" }, h("h1", {}, "Algo deu errado"),
    h("p", {}, error.message || "Erro inesperado."), h("button", { type: "button", onclick: retry }, "Tentar de novo"));
}

// Builds the shell, then runs the page's loader. The loader returns the
// nodes to show; any failure becomes a readable card with a retry button.
export function runPage(title, loader) {
  document.title = `${title} · Audiovisual BRASA`;
  const main = h("main", { class: "page" });
  document.body.replaceChildren(topbar(), main);
  async function load() {
    fill(main, h("p", { class: "help" }, "Carregando…"));
    try {
      fill(main, await loader());
    } catch (error) {
      fill(main, failureCard(error, load));
    }
  }
  load();
}

export function requireAdmin() {
  if (adminSession.isActive()) return true;
  location.href = link(`admin/entrar.html?next=${encodeURIComponent(location.pathname + location.search)}`);
  return false;
}

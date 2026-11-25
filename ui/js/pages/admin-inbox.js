import { requestsApi } from "../api.js";
import { formatDate, h, link, requireAdmin, runPage, statusBadge, waitingOptions } from "../page.js";

function select(name, label, allLabel, options, current) {
  return h("div", { class: "field" }, h("label", { for: name }, label),
    h("select", { id: name, name }, h("option", { value: "" }, allLabel),
      options.map(([value, text]) => h("option", { value, selected: String(value) === current }, text))));
}

if (requireAdmin()) {
  runPage("Pedidos", async () => {
    const filters = new URLSearchParams(location.search);
    const [catalog, rows, workload] = await Promise.all([
      requestsApi.get("/catalog", waitingOptions),
      requestsApi.get(`/admin/requests?${filters}`, { ...waitingOptions, admin: true }),
      requestsApi.get("/admin/workload", { ...waitingOptions, admin: true }),
    ]);
    const typeLabel = (code) => (catalog.types.find((t) => t.code === code) || { label: code }).label;
    const diretoria = (id) => (catalog.diretorias.find((d) => d.id === id) || { name: "—" }).name;

    return [
      h("h1", {}, "Pedidos"),
      h("section", { class: "card" }, h("h3", {}, "Carga por pessoa"),
        h("p", {}, workload.analysts.map((a) =>
          [h("span", { class: `badge${a.open > workload.threshold ? " badge-rush" : ""}` }, `${a.name}: ${a.open}`), " "]))),
      h("form", { class: "filters", method: "get" },
        select("status", "Status", "Todos", catalog.statuses.map((s) => [s.value, s.label]), filters.get("status") || ""),
        select("type_code", "Tipo", "Todos", catalog.types.map((t) => [t.code, t.label]), filters.get("type_code") || ""),
        select("diretoria_id", "Diretoria", "Todas", catalog.diretorias.map((d) => [d.id, d.name]), filters.get("diretoria_id") || ""),
        select("analyst_id", "Responsável", "Todos", catalog.analysts.map((a) => [a.id, a.name]), filters.get("analyst_id") || ""),
        h("button", { type: "submit", class: "button-secondary" }, "Filtrar")),
      h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, ["Código", "Título", "Tipo", "Diretoria", "Prazo", "Status", "Briefing"].map((c) => h("th", {}, c)))),
        h("tbody", {}, rows.length ? rows.map((r) => h("tr", {},
          h("td", {}, h("a", { href: `${link("admin/pedido.html")}?id=${r.id}` }, r.public_code)),
          h("td", {}, r.title), h("td", {}, typeLabel(r.type_code)), h("td", {}, diretoria(r.diretoria_id)),
          h("td", {}, formatDate(r.needed_by), r.rush ? [" ", h("span", { class: "badge badge-rush" }, "curto")] : null),
          h("td", {}, statusBadge(r.status, r.status_label)), h("td", {}, `${r.briefing_score}%`)))
          : h("tr", {}, h("td", { colspan: "7" }, "Nenhum pedido com esses filtros."))))),
    ];
  });
}

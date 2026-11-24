// Metrics come from both services and are shown side by side (ADR-6). If
// the feedback service is down, its cards say so and the request metrics
// still show. The only join across the seam, briefing score by outcome, is
// done here from the two halves each service publishes.

import { ApiError, feedbackApi, requestsApi } from "../api.js";
import { h, number, percent, requireAdmin, runPage, waitingOptions } from "../page.js";

const adminCall = { ...waitingOptions, admin: true };

function ratingTable(title, dimensions, rows) {
  const groups = Object.entries(rows);
  return h("section", { class: "card" }, h("h3", {}, title), groups.length
    ? h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, h("th"), dimensions.map((d) => h("th", {}, d.label)))),
        h("tbody", {}, groups.map(([group, averages]) =>
          h("tr", {}, h("td", {}, group), dimensions.map((d) => h("td", {}, number(averages[d.key]))))))))
    : h("p", {}, "Ainda sem avaliações."));
}

export function averageScoreByOutcome(briefingScores, requesterOutcomes) {
  const sums = {};
  for (const [requestId, outcome] of Object.entries(requesterOutcomes)) {
    if (!(requestId in briefingScores)) continue;
    sums[outcome] = sums[outcome] || { total: 0, count: 0 };
    sums[outcome].total += briefingScores[requestId];
    sums[outcome].count += 1;
  }
  return Object.fromEntries(Object.entries(sums).map(([o, s]) => [o, s.total / s.count]));
}

function requestCards(m) {
  const largest = Math.max(1, ...m.by_status.map((s) => s.count));
  return [
    h("section", { class: "card" }, h("h3", {}, "Pedidos por status"), m.by_status.length
      ? m.by_status.map((s) => h("div", { class: "bar-row" }, h("span", {}, s.label),
          h("div", { class: "bar", style: `width: ${Math.round((s.count / largest) * 100)}%` }), h("span", {}, s.count)))
      : h("p", {}, "Nenhum pedido ainda.")),
    h("section", { class: "card" }, h("h3", {}, "Tempo de produção (mediana, dias do aceite à entrega)"),
      Object.keys(m.median_turnaround_by_type).length
        ? Object.entries(m.median_turnaround_by_type).map(([type, days]) => h("p", {}, `${type}: `, h("strong", {}, number(days))))
        : h("p", {}, "Nenhuma entrega ainda.")),
  ];
}

function feedbackCards(requests, feedback) {
  if (feedback === null) {
    return h("p", { class: "notice notice-error" }, "As métricas de avaliação estão indisponíveis no momento (serviço de avaliação fora do ar).");
  }
  const scores = averageScoreByOutcome(requests.briefing_scores, feedback.requester_outcomes);
  return [
    h("section", { class: "card" }, h("h3", {}, "Resultado das avaliações (quem pediu)"),
      feedback.outcome_counts.map((o) => h("p", {}, `${o.label}: `, h("strong", {}, o.count),
        o.outcome in scores ? ` · briefing médio ${number(scores[o.outcome])}%` : ""))),
    ratingTable("Notas médias por tipo", feedback.dimensions, feedback.ratings_by_type),
    ratingTable("Notas médias por diretoria", feedback.dimensions, feedback.ratings_by_diretoria),
  ];
}

if (requireAdmin()) {
  runPage("Métricas", async () => {
    const [requests, feedback] = await Promise.all([
      requestsApi.get("/admin/metrics", adminCall),
      feedbackApi.get("/admin/metrics", { admin: true }).catch((error) => {
        if (error instanceof ApiError && error.status === 401) throw error;
        return null;
      }),
    ]);
    return [
      h("h1", {}, "Métricas"),
      h("section", { class: "card" }, h("h3", {}, "Visão geral"),
        h("p", {}, h("strong", {}, requests.total_requests), " pedidos · prazo curto em ", h("strong", {}, percent(requests.rush_share)),
          " · entregues no prazo: ", h("strong", {}, percent(requests.on_time_rate)),
          " · taxa de resposta das avaliações: ", h("strong", {}, feedback ? percent(feedback.response_rate) : "—"),
          " · briefing médio: ", h("strong", {}, requests.average_score === null ? "—" : `${number(requests.average_score)}%`))),
      requestCards(requests),
      feedbackCards(requests, feedback),
    ];
  });
}

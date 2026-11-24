import { h, link, runPage } from "../page.js";

runPage("AV Desk", async () => [
  h("section", { class: "hero" },
    h("h1", {}, "Pedidos de audiovisual da BRASA"),
    h("p", {}, "Precisa de um vídeo? Conte pra gente o que você imagina. Um bom briefing é o caminho mais curto para um vídeo que acerta de primeira.")),
  h("section", { class: "gate" },
    h("h2", {}, "O que você precisa?"),
    h("div", { class: "gate-options" },
      h("article", { class: "card" }, h("h3", {}, "Um vídeo"),
        h("p", {}, "Teaser, vídeo institucional, vídeo para redes sociais fora do calendário editorial ou outro formato."),
        h("a", { class: "button", href: link("pedido-novo.html") }, "Começar o briefing")),
      h("article", { class: "card card-muted" }, h("h3", {}, "Um post regular do calendário editorial"),
        h("p", {}, "Posts de feed, stories, reels e TikToks do calendário seguem o fluxo de briefing da Comunicação no ClickUp. Esses pedidos não entram por aqui.")))),
]);

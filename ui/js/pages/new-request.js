import { ApiError, requestsApi } from "../api.js";
import { briefingForm } from "../briefing-form.js";
import { flash, h, link, runPage, waitingOptions } from "../page.js";

runPage("Novo pedido", async () => {
  const catalog = await requestsApi.get("/catalog", waitingOptions);
  const holder = h("div");

  function show(briefing, errors) {
    holder.replaceChildren(briefingForm({ catalog, briefing, errors, submitLabel: "Enviar briefing", onSubmit: submit }));
  }

  async function submit(briefing) {
    try {
      const created = await requestsApi.post("/requests", briefing, waitingOptions);
      // The token travels in the fragment, which browsers never send to the
      // static host, so it stays out of server logs and Referer headers.
      sessionStorage.setItem("avdesk-flash", "Pedido enviado! Guarde este link: é por ele que você acompanha o seu pedido.");
      location.href = `${link("pedido.html")}#t=${encodeURIComponent(created.tracking_token)}`;
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        show(briefing, error.body.errors);
        window.scrollTo(0, 0);
      } else {
        flash(error.message || "Não foi possível enviar agora. Tente de novo em instantes.", "error");
      }
    }
  }

  show({}, {});
  return [
    h("h1", {}, "Novo pedido de vídeo"),
    h("p", {}, "Quanto mais contexto você der, menos idas e vindas teremos. Os campos com ", h("span", { class: "required" }), " são obrigatórios."),
    holder,
  ];
});

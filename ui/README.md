# ui/ — the static AV Desk pages

Plain HTML, CSS and ES modules, no build step: the folder is uploaded as is
to the storage static website (`$web`), and `docker compose` serves it with a
stock nginx image. The pages only call the two services over HTTPS/JSON.

- `config.js` holds the two service base URLs. The committed file points at the
  local compose ports; the CD pipeline overwrites it with the Azure URLs.
- `js/api.js` is the only module that talks HTTP: 40 s timeout per call,
  quiet retries while a service wakes from scale-to-zero, the admin token in
  `sessionStorage`, sent as `Authorization: Bearer`.
- `js/page.js` builds the page shell and turns any failure into a readable card
  with a retry button, never a blank page.
- `js/pages/<page>.js` is one script per HTML page.

Rules: text goes into the DOM only through `textContent` (the `h()` helper),
so data typed by users cannot inject markup. Secret tokens (tracking and
feedback links) travel in the URL fragment (`#t=`), which browsers never send
to the static host. Validation and scoring in the browser are previews; the
services decide.

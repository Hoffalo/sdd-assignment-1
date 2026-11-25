// The only module that talks HTTP. Every call has a timeout, and a service
// that is waking up from scale-to-zero is retried with a visible notice
// instead of leaving the page blank or hanging.

const config = window.AVDESK_CONFIG;

// Container Apps holds the first request after idle for about 30 s and then
// answers 503 if the container is not ready, so wait a little longer than that.
const TIMEOUT_MS = 40000;
// A cold start plus a paused database can take a minute or more; two quiet
// retries cover most of it before the reader is asked to try again.
const RETRIES_WHILE_STARTING = 2;
const RETRY_DELAY_MS = 5000;
const STARTING_STATUSES = new Set([502, 503, 504]);

const ADMIN_TOKEN_KEY = "avdesk-admin-token";

export class ServiceStarting extends Error {}

export class ApiError extends Error {
  constructor(status, body) {
    super((body && body.error) || `HTTP ${status}`);
    this.status = status;
    this.body = body || {};
  }
}

// sessionStorage, not localStorage: the token dies with the tab, so a shared
// computer does not stay logged in. It is never put in a cookie or a URL.
export const adminSession = {
  token() {
    try { return sessionStorage.getItem(ADMIN_TOKEN_KEY); } catch (e) { return null; }
  },
  start(token) {
    try { sessionStorage.setItem(ADMIN_TOKEN_KEY, token); } catch (e) { /* private mode: login lasts this page */ }
  },
  end() {
    try { sessionStorage.removeItem(ADMIN_TOKEN_KEY); } catch (e) { /* nothing stored */ }
  },
  isActive() { return Boolean(this.token()); },
};

function wait(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

async function fetchOnce(url, init) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function call(baseUrl, path, { method = "GET", body, admin = false, onStarting } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (admin && adminSession.token()) headers.Authorization = `Bearer ${adminSession.token()}`;
  const init = { method, headers, body: body === undefined ? undefined : JSON.stringify(body) };

  for (let attempt = 0; ; attempt++) {
    let response;
    try {
      response = await fetchOnce(baseUrl + path, init);
    } catch (networkOrTimeout) {
      response = null;
    }
    if (response && !STARTING_STATUSES.has(response.status)) {
      const payload = await response.json().catch(() => ({}));
      if (response.ok) return payload;
      if (response.status === 401 && admin) adminSession.end();
      throw new ApiError(response.status, payload);
    }
    if (attempt >= RETRIES_WHILE_STARTING) throw new ServiceStarting();
    if (onStarting) onStarting();
    await wait(RETRY_DELAY_MS);
  }
}

function client(baseUrl) {
  return {
    get: (path, options) => call(baseUrl, path, options),
    post: (path, body, options) => call(baseUrl, path, { ...options, method: "POST", body }),
    put: (path, body, options) => call(baseUrl, path, { ...options, method: "PUT", body }),
  };
}

export const requestsApi = client(config.requestsUrl);
export const feedbackApi = client(config.feedbackUrl);

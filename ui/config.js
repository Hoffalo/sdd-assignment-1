// Where the two services live. This file is the local default (the ports
// docker compose publishes); the CD pipeline overwrites it with the Azure
// Container Apps URLs when it uploads the UI, so no URL is hardcoded in code.
window.AVDESK_CONFIG = {
  requestsUrl: "http://localhost:8001",
  feedbackUrl: "http://localhost:8002",
};

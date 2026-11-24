"""Cross-origin access for exactly one origin: the static UI.

The browser loads the UI from the storage static website and calls this
service on another host, so without these headers it would refuse to read
the answers. Only CORS_ORIGIN is echoed back; any other site gets no CORS
headers and the browser blocks it. Written by hand (about 20 lines) instead
of adding flask-cors, to stay well under the dependency cap.
"""
from flask import Flask, Response, request

ALLOWED_METHODS = "GET, POST, PUT, OPTIONS"
ALLOWED_HEADERS = "Authorization, Content-Type"
# Lets the browser reuse a preflight answer for 10 minutes instead of asking
# before every admin call.
PREFLIGHT_MAX_AGE_S = "600"


def install(app: Flask, allowed_origin: str) -> None:
    @app.before_request
    def answer_preflight():
        if request.method == "OPTIONS":
            return Response(status=204)
        return None

    @app.after_request
    def add_cors_headers(response: Response) -> Response:
        response.vary.add("Origin")
        if request.headers.get("Origin") != allowed_origin:
            return response
        response.headers["Access-Control-Allow-Origin"] = allowed_origin
        if request.method == "OPTIONS":
            response.headers["Access-Control-Allow-Methods"] = ALLOWED_METHODS
            response.headers["Access-Control-Allow-Headers"] = ALLOWED_HEADERS
            response.headers["Access-Control-Max-Age"] = PREFLIGHT_MAX_AGE_S
        return response

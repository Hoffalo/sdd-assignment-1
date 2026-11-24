"""One stdout line per request: method, path, status and duration.

Container Apps ships stdout to Log Analytics, so this line is how a slow or
failing request is found in production. perf_counter is used directly
because it measures elapsed time, not the business "now" the Clock owns.
"""
import logging
import time

from flask import Flask, Response, g, request

log = logging.getLogger(__name__)


def install(app: Flask) -> None:
    @app.before_request
    def start_timer() -> None:
        g.request_started = time.perf_counter()

    @app.after_request
    def log_request(response: Response) -> Response:
        elapsed_ms = (time.perf_counter() - g.get("request_started", time.perf_counter())) * 1000
        log.info("%s %s %s %.1fms", request.method, request.path, response.status_code, elapsed_ms)
        return response

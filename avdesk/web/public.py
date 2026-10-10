"""Public pages: landing with the scope gate and the health check."""
from flask import Blueprint, jsonify, render_template

blueprint = Blueprint("public", __name__)


@blueprint.get("/")
def landing():
    return render_template("landing.html")


@blueprint.get("/healthz")
def healthz():
    return jsonify(status="ok")

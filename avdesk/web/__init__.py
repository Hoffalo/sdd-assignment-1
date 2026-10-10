"""Flask glue only: parse HTTP input, call a facade, render a template."""
from flask import current_app


def services():
    return current_app.extensions["avdesk"]

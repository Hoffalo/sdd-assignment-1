"""CSRF protection for every POST, and the admin session."""
import hmac
import secrets

from flask import Flask, abort, request, session

CSRF_FIELD = "csrf_token"
ADMIN_FLAG = "is_admin"


def csrf_token() -> str:
    if CSRF_FIELD not in session:
        session[CSRF_FIELD] = secrets.token_urlsafe(32)
    return session[CSRF_FIELD]


def install(app: Flask) -> None:
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def reject_forged_posts():
        # Without this, another site could make a logged-in admin's browser
        # submit our forms (cross-site request forgery).
        if request.method == "POST":
            sent = request.form.get(CSRF_FIELD, "")
            if not sent or not hmac.compare_digest(sent, session.get(CSRF_FIELD, "")):
                abort(400)


def password_matches(given: str, expected: str) -> bool:
    # compare_digest takes the same time however many characters match, so
    # response timing reveals nothing about the password.
    return hmac.compare_digest(given.encode(), expected.encode())


def is_admin() -> bool:
    return session.get(ADMIN_FLAG) is True


def log_in() -> None:
    session.clear()
    session[ADMIN_FLAG] = True


def log_out() -> None:
    session.clear()

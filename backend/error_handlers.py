"""
Every JSON error response follows the same shape: {"error": "...", "message": "..."}.
HTML routes (the public bio page, the redirect 404) fall through to Flask's
default/simple text handling instead, since a browser navigating there wants
a page, not JSON.
"""
from flask import jsonify, request
from extensions import db


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify(error="not_found", message=str(e.description) or "Resource not found."), 404
        return e, 404

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify(
            error="rate_limited", message="Too many requests. Please wait a moment and try again."
        ), 429

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        app.logger.exception("Unhandled server error")
        if request.path.startswith("/api/") or request.path.startswith("/r/"):
            return jsonify(error="server_error", message="Something went wrong on our end."), 500
        return e, 500

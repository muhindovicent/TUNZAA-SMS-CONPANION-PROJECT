"""Consistent API error responses."""

from __future__ import annotations

from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import HTTPException

import structlog

logger = structlog.get_logger(__name__)


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def error_response(code: str, message: str, status: int) -> Response:
    response = jsonify({"error": {"code": code, "message": message}})
    response.status_code = status
    return response


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError) -> Response:
        return error_response(error.code, error.message, error.status)

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException) -> Response:
        code = (error.name or "http_error").lower().replace(" ", "_")
        message = error.description or "Request failed."
        return error_response(code, message, error.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception) -> Response:
        logger.exception(
            "unhandled_request_error",
            path=request.path,
            method=request.method,
            error_type=type(error).__name__,
        )
        return error_response("internal_error", "An unexpected error occurred.", 500)

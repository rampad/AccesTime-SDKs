"""Excepciones tipadas para que tu código pueda diferenciar errores."""
from __future__ import annotations

from typing import Any


class AccesTimeError(Exception):
    """Base. Captura status code + detail del body de respuesta."""

    def __init__(self, status_code: int, detail: Any = None, response_body: str = ""):
        self.status_code = status_code
        self.detail = detail
        self.response_body = response_body
        super().__init__(f"HTTP {status_code}: {detail or response_body[:200]}")


class BadRequestError(AccesTimeError):
    """400 — request mal formado."""


class AuthError(AccesTimeError):
    """401 — API key inválida, expirada o revocada."""


class ForbiddenError(AccesTimeError):
    """403 — scope insuficiente o plan sin api_access."""


class NotFoundError(AccesTimeError):
    """404 — recurso no existe."""


class ConflictError(AccesTimeError):
    """409 — duplicado, idempotency-key conflict, etc."""


class ValidationError(AccesTimeError):
    """422 — Pydantic validation failure. self.detail es la lista de errores."""


class RateLimitError(AccesTimeError):
    """429 por rpm. Tiene .retry_after en segundos."""

    def __init__(self, status_code, detail, response_body, retry_after: int | None = None):
        super().__init__(status_code, detail, response_body)
        self.retry_after = retry_after


class QuotaExceededError(AccesTimeError):
    """429 por cuota mensual agotada. Esperar hasta el próximo mes."""


class ServerError(AccesTimeError):
    """5xx."""


def from_response(status_code: int, body_text: str, headers: dict) -> AccesTimeError:
    """Construye la excepción adecuada según el status code y body."""
    import json
    try:
        body = json.loads(body_text)
        detail = body.get("detail")
    except Exception:
        detail = None

    if status_code == 400: return BadRequestError(status_code, detail, body_text)
    if status_code == 401: return AuthError(status_code, detail, body_text)
    if status_code == 403: return ForbiddenError(status_code, detail, body_text)
    if status_code == 404: return NotFoundError(status_code, detail, body_text)
    if status_code == 409: return ConflictError(status_code, detail, body_text)
    if status_code == 422: return ValidationError(status_code, detail, body_text)
    if status_code == 429:
        # Distinguir cuota mensual vs rate limit por el contenido del detail
        if isinstance(detail, str) and "Cuota" in detail:
            return QuotaExceededError(status_code, detail, body_text)
        retry = int(headers.get("retry-after", 0)) or None
        return RateLimitError(status_code, detail, body_text, retry_after=retry)
    if 500 <= status_code < 600: return ServerError(status_code, detail, body_text)
    return AccesTimeError(status_code, detail, body_text)

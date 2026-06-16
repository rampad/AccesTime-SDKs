"""
Helpers para receptores de webhooks: verificar la firma HMAC y bloquear replays.

Uso con FastAPI/Flask:

    from accestime import verify_webhook_signature

    @app.post("/accestime-webhook")
    async def handle(request: Request):
        body = await request.body()
        try:
            verify_webhook_signature(
                secret=SECRET,
                body=body,
                signature=request.headers["X-AccesTime-Signature"],
                timestamp=int(request.headers["X-AccesTime-Timestamp"]),
            )
        except InvalidSignature:
            raise HTTPException(401, "bad signature")
"""
from __future__ import annotations

import hashlib
import hmac
import time


REPLAY_WINDOW_SECONDS = 300  # 5 min


class InvalidSignature(Exception):
    """Raised when the signature does NOT match or the timestamp is too old."""


def verify_webhook_signature(
    *,
    secret: str,
    body: bytes,
    signature: str,
    timestamp: int,
    tolerance_seconds: int = REPLAY_WINDOW_SECONDS,
) -> None:
    """Lanza InvalidSignature si la firma no es válida o el timestamp es viejo."""
    if abs(time.time() - timestamp) > tolerance_seconds:
        raise InvalidSignature(f"Timestamp {timestamp} fuera de la ventana de {tolerance_seconds}s")

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + (body or b""),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature or ""):
        raise InvalidSignature("Firma HMAC no coincide")

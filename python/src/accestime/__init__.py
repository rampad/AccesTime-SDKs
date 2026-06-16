"""SDK oficial Python para la API de AccesTime.

Uso típico:

    from accestime import AccesTime

    client = AccesTime(tenant="acme", api_key="at_live_xxx")
    employees = client.employees.list(limit=50)
    for emp in client.employees.iter():  # auto-paginate
        print(emp["nombres"])

Versión async:

    from accestime import AsyncAccesTime
    async with AsyncAccesTime(tenant="acme", api_key="at_live_xxx") as client:
        employees = await client.employees.list(limit=50)
"""
from .client import AccesTime, AsyncAccesTime
from .webhooks_verify import verify_webhook_signature, InvalidSignature
from .errors import (
    AccesTimeError,
    AuthError,
    BadRequestError,
    NotFoundError,
    QuotaExceededError,
    RateLimitError,
    ValidationError,
    ServerError,
)

__version__ = "0.1.0"
__all__ = [
    "AccesTime",
    "AsyncAccesTime",
    "verify_webhook_signature",
    "InvalidSignature",
    "AccesTimeError",
    "AuthError",
    "BadRequestError",
    "NotFoundError",
    "QuotaExceededError",
    "RateLimitError",
    "ValidationError",
    "ServerError",
]

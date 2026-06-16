"""Cliente HTTP + sub-resources."""
from __future__ import annotations

import os
import time
import uuid
from typing import Any, AsyncIterator, Iterator, Optional

import httpx

from .errors import (
    AccesTimeError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
    from_response,
)


DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
USER_AGENT = "accestime-python/0.1.0"


def _base_url(tenant: str) -> str:
    return f"https://{tenant}.accestime.com/api/v1"


def _default_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }


# ── Sync client ─────────────────────────────────────────────────────────────


class _SyncRequest:
    def __init__(self, parent: "AccesTime"):
        self._parent = parent

    def request(self, method: str, path: str, *, params=None, json=None,
                idempotency_key: Optional[str] = None) -> Any:
        url = f"{self._parent._base_url}{path}"
        headers = dict(self._parent._headers)
        if idempotency_key is None and method in ("POST", "PATCH"):
            idempotency_key = str(uuid.uuid4())
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        last_exc: Optional[Exception] = None
        for attempt in range(self._parent.max_retries + 1):
            try:
                r = self._parent._http.request(
                    method, url, params=params, json=json, headers=headers,
                )
            except httpx.RequestError as e:
                last_exc = e
                if attempt >= self._parent.max_retries:
                    raise
                time.sleep(self._backoff(attempt))
                continue

            if r.status_code < 400:
                if r.status_code == 204 or not r.content:
                    return None
                return r.json()

            # 4xx/5xx
            if r.status_code in RETRYABLE_STATUS and attempt < self._parent.max_retries:
                # No reintentar 429 si es cuota mensual (espera hasta el mes próximo)
                if r.status_code == 429 and "Cuota" in (r.text or ""):
                    raise from_response(r.status_code, r.text, dict(r.headers))
                wait = self._wait_from_response(r, attempt)
                time.sleep(wait)
                continue
            raise from_response(r.status_code, r.text, dict(r.headers))

        # No debería llegar acá
        if last_exc:
            raise last_exc
        raise AccesTimeError(0, "Max retries exhausted")

    def _backoff(self, attempt: int) -> float:
        return min(2 ** attempt * 0.5, 30.0)

    def _wait_from_response(self, r, attempt: int) -> float:
        ra = r.headers.get("retry-after")
        if ra and ra.isdigit():
            return float(ra)
        return self._backoff(attempt)


class AccesTime:
    """Cliente síncrono — usar dentro de scripts/CLI."""

    def __init__(
        self,
        tenant: Optional[str] = None,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        tenant = tenant or os.environ.get("ACCESTIME_TENANT", "")
        api_key = api_key or os.environ.get("ACCESTIME_API_KEY", "")
        if not tenant:
            raise ValueError("tenant es requerido (param o env ACCESTIME_TENANT)")
        if not api_key:
            raise ValueError("api_key es requerido (param o env ACCESTIME_API_KEY)")

        self.tenant = tenant
        self._base_url = base_url or _base_url(tenant)
        self._headers = _default_headers(api_key)
        self.max_retries = max_retries
        self._http = httpx.Client(timeout=timeout)

        self._req = _SyncRequest(self)
        self.employees = Employees(self._req)
        self.marcados = Marcados(self._req)
        self.jornadas = Jornadas(self._req)
        self.turnos = Turnos(self._req)
        self.webhooks = Webhooks(self._req)

    def close(self):
        self._http.close()

    def __enter__(self): return self
    def __exit__(self, *exc): self.close()


# ── Async client ────────────────────────────────────────────────────────────


import asyncio


class _AsyncRequest:
    def __init__(self, parent: "AsyncAccesTime"):
        self._parent = parent

    async def request(self, method: str, path: str, *, params=None, json=None,
                      idempotency_key: Optional[str] = None) -> Any:
        url = f"{self._parent._base_url}{path}"
        headers = dict(self._parent._headers)
        if idempotency_key is None and method in ("POST", "PATCH"):
            idempotency_key = str(uuid.uuid4())
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(self._parent.max_retries + 1):
            try:
                r = await self._parent._http.request(
                    method, url, params=params, json=json, headers=headers,
                )
            except httpx.RequestError:
                if attempt >= self._parent.max_retries:
                    raise
                await asyncio.sleep(min(2 ** attempt * 0.5, 30.0))
                continue

            if r.status_code < 400:
                if r.status_code == 204 or not r.content:
                    return None
                return r.json()

            if r.status_code in RETRYABLE_STATUS and attempt < self._parent.max_retries:
                if r.status_code == 429 and "Cuota" in (r.text or ""):
                    raise from_response(r.status_code, r.text, dict(r.headers))
                ra = r.headers.get("retry-after")
                wait = float(ra) if ra and ra.isdigit() else min(2 ** attempt * 0.5, 30.0)
                await asyncio.sleep(wait)
                continue
            raise from_response(r.status_code, r.text, dict(r.headers))


class AsyncAccesTime:
    """Cliente async — usar en código asyncio."""

    def __init__(
        self,
        tenant: Optional[str] = None,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        tenant = tenant or os.environ.get("ACCESTIME_TENANT", "")
        api_key = api_key or os.environ.get("ACCESTIME_API_KEY", "")
        if not tenant or not api_key:
            raise ValueError("tenant y api_key son requeridos")
        self.tenant = tenant
        self._base_url = base_url or _base_url(tenant)
        self._headers = _default_headers(api_key)
        self.max_retries = max_retries
        self._http = httpx.AsyncClient(timeout=timeout)

        self._req = _AsyncRequest(self)
        self.employees = AsyncEmployees(self._req)
        self.marcados = AsyncMarcados(self._req)
        self.jornadas = AsyncJornadas(self._req)
        self.turnos = AsyncTurnos(self._req)
        self.webhooks = AsyncWebhooks(self._req)

    async def aclose(self): await self._http.aclose()
    async def __aenter__(self): return self
    async def __aexit__(self, *exc): await self.aclose()


# ── Resources (sync) ────────────────────────────────────────────────────────


class _PaginatedResource:
    """Mixin sync: añade .iter() que pagina automáticamente sobre .list()."""
    _req: _SyncRequest
    _path: str

    def _list(self, **params) -> dict:
        return self._req.request("GET", self._path, params=params)

    def iter(self, **params) -> Iterator[dict]:
        """Itera sobre todas las páginas. Yields cada ítem individualmente."""
        cursor = None
        while True:
            p = dict(params)
            if cursor:
                p["cursor"] = cursor
            page = self._list(**p)
            for item in page.get("data", []):
                yield item
            pag = page.get("pagination", {})
            if not pag.get("has_more"):
                return
            cursor = pag.get("next_cursor")
            if not cursor:
                return


class Employees(_PaginatedResource):
    _path = "/employees"
    def __init__(self, req: _SyncRequest): self._req = req

    def list(self, *, limit=50, cursor=None, status=None, local_id=None, updated_since=None) -> dict:
        params = {"limit": limit}
        if cursor: params["cursor"] = cursor
        if status: params["status"] = status
        if local_id: params["local_id"] = local_id
        if updated_since: params["updated_since"] = updated_since
        return self._list(**params)

    def get(self, employee_id: int) -> dict:
        return self._req.request("GET", f"{self._path}/{employee_id}")

    def create(self, **kwargs) -> dict:
        return self._req.request("POST", self._path, json=kwargs,
                                 idempotency_key=kwargs.pop("idempotency_key", None))

    def create_bulk(self, employees: list[dict], *, suppress_webhooks: bool = False,
                    idempotency_key: Optional[str] = None) -> dict:
        return self._req.request("POST", f"{self._path}:bulk",
                                 json={"employees": employees, "suppress_webhooks": suppress_webhooks},
                                 idempotency_key=idempotency_key)

    def update(self, employee_id: int, **kwargs) -> dict:
        return self._req.request("PATCH", f"{self._path}/{employee_id}", json=kwargs,
                                 idempotency_key=kwargs.pop("idempotency_key", None))


class Marcados(_PaginatedResource):
    _path = "/marcados"
    def __init__(self, req: _SyncRequest): self._req = req

    def list(self, *, desde: str, hasta: str, limit=50, cursor=None,
             employee_id=None, local_id=None, tipo_registro=None) -> dict:
        params = {"desde": desde, "hasta": hasta, "limit": limit}
        if cursor: params["cursor"] = cursor
        if employee_id: params["employee_id"] = employee_id
        if local_id: params["local_id"] = local_id
        if tipo_registro: params["tipo_registro"] = tipo_registro
        return self._list(**params)

    def create(self, **kwargs) -> dict:
        return self._req.request("POST", self._path, json=kwargs,
                                 idempotency_key=kwargs.pop("idempotency_key", None))

    def create_bulk(self, marcados: list[dict], *, suppress_webhooks: bool = False,
                    idempotency_key: Optional[str] = None) -> dict:
        return self._req.request("POST", f"{self._path}:bulk",
                                 json={"marcados": marcados, "suppress_webhooks": suppress_webhooks},
                                 idempotency_key=idempotency_key)


class Jornadas(_PaginatedResource):
    _path = "/jornadas"
    def __init__(self, req: _SyncRequest): self._req = req

    def list(self, *, desde: str, hasta: str, limit=50, cursor=None,
             employee_id=None, local_id=None, estado=None) -> dict:
        params = {"desde": desde, "hasta": hasta, "limit": limit}
        if cursor: params["cursor"] = cursor
        if employee_id: params["employee_id"] = employee_id
        if local_id: params["local_id"] = local_id
        if estado: params["estado"] = estado
        return self._list(**params)


class Turnos(_PaginatedResource):
    _path = "/turnos"
    def __init__(self, req: _SyncRequest): self._req = req

    def list(self, *, limit=50, cursor=None, local_id=None, activo=None) -> dict:
        params = {"limit": limit}
        if cursor: params["cursor"] = cursor
        if local_id: params["local_id"] = local_id
        if activo is not None: params["activo"] = activo
        return self._list(**params)


class Webhooks:
    _path = "/webhooks"
    def __init__(self, req: _SyncRequest): self._req = req

    def list(self, include_revoked: bool = False) -> list[dict]:
        return self._req.request("GET", self._path, params={"include_revoked": include_revoked})

    def create(self, *, name: str, url: str, events: list[str]) -> dict:
        return self._req.request("POST", self._path, json={"name": name, "url": url, "events": events})

    def delete(self, webhook_id: int) -> None:
        return self._req.request("DELETE", f"{self._path}/{webhook_id}")

    def deliveries(self, webhook_id: int, *, limit=50, cursor=None, status=None) -> dict:
        params = {"limit": limit}
        if cursor: params["cursor"] = cursor
        if status: params["status"] = status
        return self._req.request("GET", f"{self._path}/{webhook_id}/deliveries", params=params)


# ── Resources (async) — mismo shape, todo awaitable ─────────────────────────


class _AsyncPaginatedResource:
    _req: _AsyncRequest
    _path: str

    async def _list(self, **params) -> dict:
        return await self._req.request("GET", self._path, params=params)

    async def iter(self, **params) -> AsyncIterator[dict]:
        cursor = None
        while True:
            p = dict(params)
            if cursor:
                p["cursor"] = cursor
            page = await self._list(**p)
            for item in page.get("data", []):
                yield item
            pag = page.get("pagination", {})
            if not pag.get("has_more"):
                return
            cursor = pag.get("next_cursor")
            if not cursor:
                return


class AsyncEmployees(_AsyncPaginatedResource):
    _path = "/employees"
    def __init__(self, req): self._req = req

    async def list(self, **params): return await self._list(**params)
    async def get(self, employee_id): return await self._req.request("GET", f"{self._path}/{employee_id}")
    async def create(self, **kwargs):
        idem = kwargs.pop("idempotency_key", None)
        return await self._req.request("POST", self._path, json=kwargs, idempotency_key=idem)
    async def create_bulk(self, employees, *, suppress_webhooks=False, idempotency_key=None):
        return await self._req.request("POST", f"{self._path}:bulk",
                                       json={"employees": employees, "suppress_webhooks": suppress_webhooks},
                                       idempotency_key=idempotency_key)
    async def update(self, employee_id, **kwargs):
        idem = kwargs.pop("idempotency_key", None)
        return await self._req.request("PATCH", f"{self._path}/{employee_id}", json=kwargs, idempotency_key=idem)


class AsyncMarcados(_AsyncPaginatedResource):
    _path = "/marcados"
    def __init__(self, req): self._req = req

    async def list(self, **params): return await self._list(**params)
    async def create(self, **kwargs):
        idem = kwargs.pop("idempotency_key", None)
        return await self._req.request("POST", self._path, json=kwargs, idempotency_key=idem)
    async def create_bulk(self, marcados, *, suppress_webhooks=False, idempotency_key=None):
        return await self._req.request("POST", f"{self._path}:bulk",
                                       json={"marcados": marcados, "suppress_webhooks": suppress_webhooks},
                                       idempotency_key=idempotency_key)


class AsyncJornadas(_AsyncPaginatedResource):
    _path = "/jornadas"
    def __init__(self, req): self._req = req
    async def list(self, **params): return await self._list(**params)


class AsyncTurnos(_AsyncPaginatedResource):
    _path = "/turnos"
    def __init__(self, req): self._req = req
    async def list(self, **params): return await self._list(**params)


class AsyncWebhooks:
    _path = "/webhooks"
    def __init__(self, req): self._req = req

    async def list(self, include_revoked=False):
        return await self._req.request("GET", self._path, params={"include_revoked": include_revoked})
    async def create(self, *, name, url, events):
        return await self._req.request("POST", self._path, json={"name": name, "url": url, "events": events})
    async def delete(self, webhook_id):
        return await self._req.request("DELETE", f"{self._path}/{webhook_id}")
    async def deliveries(self, webhook_id, **params):
        return await self._req.request("GET", f"{self._path}/{webhook_id}/deliveries", params=params)

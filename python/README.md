# accestime-python

SDK oficial Python para la API de AccesTime.

## Instalación

```bash
pip install accestime
```

## Quickstart

```python
from accestime import AccesTime

client = AccesTime(tenant="acme", api_key="at_live_xxx")

# Listar empleados (con paginación automática)
for emp in client.employees.iter(limit=100):
    print(emp["nombres"], emp["apellidos"])

# Fichaje
m = client.marcados.create(
    employee_id=1,
    tipo_marcado_id=1,
    local_id=1,
    latitud=-34.6,
    longitud=-58.4,
)
print(f"Creado marcado #{m['id']}")

# Idempotency-Key automático en POST/PATCH (se puede sobrescribir)
m = client.marcados.create(
    employee_id=1, tipo_marcado_id=1, local_id=1,
    latitud=-34.6, longitud=-58.4,
    idempotency_key="batch-2026-01-01-emp-1",
)
```

## Async

```python
import asyncio
from accestime import AsyncAccesTime

async def main():
    async with AsyncAccesTime(tenant="acme", api_key="at_live_xxx") as client:
        async for emp in client.employees.iter(limit=100):
            print(emp["email"])

asyncio.run(main())
```

## Configuración por env vars

```bash
export ACCESTIME_TENANT=acme
export ACCESTIME_API_KEY=at_live_xxx
```

```python
client = AccesTime()  # toma tenant + api_key de las env vars
```

## Errores tipados

```python
from accestime import AccesTime, NotFoundError, RateLimitError, QuotaExceededError

try:
    emp = client.employees.get(999_999)
except NotFoundError:
    print("no existe")
except RateLimitError as e:
    print(f"esperar {e.retry_after}s")
except QuotaExceededError:
    print("cuota mensual agotada — esperar al mes próximo")
```

## Reintentos automáticos

Por defecto el cliente reintenta hasta 3 veces ante:
- 408, 429 (rate limit, NO cuota mensual), 500, 502, 503, 504
- Errores de red transitorios

Con backoff exponencial respetando el header `Retry-After`. El 429 por cuota
mensual NO se reintenta (no sirve, hay que esperar al próximo mes).

```python
client = AccesTime(tenant="acme", api_key="...", max_retries=5)
```

## Bulk

```python
client.marcados.create_bulk([
    {"employee_id": 1, "tipo_marcado_id": 1, "local_id": 1,
     "latitud": -34.6, "longitud": -58.4,
     "hora_evento": "2025-12-01T08:00:00-03:00"},
    # ... hasta 1000
], suppress_webhooks=True)  # útil para backfill histórico
```

## Verificar firma de webhooks

```python
from accestime import verify_webhook_signature, InvalidSignature

@app.post("/accestime-webhook")
async def handle(request):
    body = await request.body()
    try:
        verify_webhook_signature(
            secret=os.environ["WEBHOOK_SECRET"],
            body=body,
            signature=request.headers["X-AccesTime-Signature"],
            timestamp=int(request.headers["X-AccesTime-Timestamp"]),
        )
    except InvalidSignature:
        raise HTTPException(401)

    event = await request.json()
    # ...
```

## Documentación

- API: https://docs.accestime.com
- Swagger: https://api.accestime.com/swagger

## Licencia

MIT

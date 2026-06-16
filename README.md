# 🛠 AccesTime SDKs

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Node.js](https://img.shields.io/badge/Node.js-339933?style=for-the-badge&logo=node.js&logoColor=white)](https://nodejs.org/)

> **SDKs oficiales para la API pública de AccesTime — Python y JavaScript/TypeScript**

Monorepo con dos paquetes publicables que abstraen la API REST v1 de AccesTime con paginación automática, idempotency, retries, errores tipados y verificación de webhooks.

## 📦 Paquetes

| Lenguaje      | Paquete                     | Instalación                                | Versión |
|---------------|-----------------------------|--------------------------------------------|---------|
| Python ≥ 3.10 | [`accestime`](./python)     | `pip install accestime`                    | 0.1.0   |
| Node ≥ 18 / TS| [`@accestime/api-client`](./javascript) | `npm install @accestime/api-client` | 0.1.0   |

> 🧬 Ambos SDKs se mantienen en paralelo con la misma versión y feature set. Las firmas de métodos son equivalentes entre lenguajes.

## ✨ Features comunes

- ✅ **Paginación automática** vía generators (Python) / AsyncIterator (JS)
- ✅ **Idempotency-Key** autogenerada (UUID v4) en POST/PATCH, override soportado
- ✅ **Retries con backoff exponencial** ante 408, 429 (rate limit), 5xx, errores de red
- ✅ **Errores tipados** con jerarquía paralela en ambos lenguajes
- ✅ **`retry_after` / `retryAfter`** disponible en `RateLimitError`
- ✅ **Verificación HMAC** de webhooks con anti-replay window de 5 minutos
- ✅ **Env vars** `ACCESTIME_TENANT` y `ACCESTIME_API_KEY` por defecto
- ✅ Sin dependencias adicionales más allá de `httpx` (Python) y nada (JS — usa `fetch` nativo)

## 🚀 Quickstart

### Python

```python
from accestime import AccesTime

client = AccesTime(tenant="acme", api_key="at_live_xxx")

for emp in client.employees.iter(limit=100):
    print(emp["nombres"], emp["apellidos"])

client.marcados.create(
    employee_id=1,
    tipo_marcado_id=1,
    local_id=1,
    latitud=-34.60376,
    longitud=-58.38157,
)
```

### JavaScript / TypeScript

```ts
import { AccesTime } from '@accestime/api-client'

const client = new AccesTime({ tenant: 'acme', apiKey: 'at_live_xxx' })

for await (const emp of client.employees.iter({ limit: 100 })) {
  console.log(emp.nombres, emp.apellidos)
}

await client.marcados.create({
  employee_id: 1, tipo_marcado_id: 1, local_id: 1,
  latitud: -34.60376, longitud: -58.38157,
})
```

## 🔐 Verificación de firma de webhooks

### Python

```python
from accestime import verify_webhook_signature, InvalidSignature

try:
    verify_webhook_signature(
        secret=SECRET,
        body=raw_body,
        signature=request.headers["X-AccesTime-Signature"],
        timestamp=int(request.headers["X-AccesTime-Timestamp"]),
    )
except InvalidSignature:
    raise HTTPException(401)
```

### JavaScript

```ts
import { verifyWebhookSignature, InvalidSignature } from '@accestime/api-client/webhooks'

try {
  verifyWebhookSignature({
    secret: process.env.WEBHOOK_SECRET!,
    body: req.body,
    signature: req.header('X-AccesTime-Signature')!,
    timestamp: parseInt(req.header('X-AccesTime-Timestamp')!, 10),
  })
} catch (e) {
  if (e instanceof InvalidSignature) return res.status(401).send()
}
```

## 📖 Documentación

- 📚 **API completa**: https://docs.accestime.com
- 🔍 **Swagger UI**: https://api.accestime.com/swagger
- 📦 **OpenAPI spec**: https://api.accestime.com/public-openapi.json

## 🧪 Tests

```bash
# Python — el README de python/ tiene más ejemplos
cd python && pip install -e .

# JavaScript — smoke test en test/
cd javascript && pnpm install && pnpm build
SDK_TOKEN=at_test_xxx node test/smoke.mjs
```

## 📜 Versionado

[SemVer](https://semver.org/lang/es/):

- `0.x.y` — beta, breaking changes posibles entre minors
- `1.0.0` (próximo) — API estable
- Nuevos endpoints son **minor bump**
- Cambios de defaults o renames de métodos son **major bump**

## 📜 License

MIT — ver [`LICENSE`](./LICENSE) en cada paquete.

## 📬 Soporte

[soporte@accestime.com](mailto:soporte@accestime.com)

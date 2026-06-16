# @accestime/api-client

SDK oficial JavaScript/TypeScript para la API de AccesTime.

## Instalación

```bash
npm install @accestime/api-client
# o pnpm/yarn
```

Requiere Node.js 18+ o un runtime moderno con `fetch` global.

## Quickstart

```ts
import { AccesTime } from '@accestime/api-client'

const client = new AccesTime({ tenant: 'acme', apiKey: 'at_live_xxx' })

// Listar empleados (paginación automática vía AsyncIterator)
for await (const emp of client.employees.iter({ limit: 100 })) {
  console.log(emp.nombres, emp.apellidos)
}

// Fichaje
const m = await client.marcados.create({
  employee_id: 1,
  tipo_marcado_id: 1,
  local_id: 1,
  latitud: -34.60376,
  longitud: -58.38157,
})
console.log(`Creado marcado #${m.id}`)
```

## Configuración por env vars

```bash
export ACCESTIME_TENANT=acme
export ACCESTIME_API_KEY=at_live_xxx
```

```ts
const client = new AccesTime()  // toma de las env vars
```

## Errores tipados

```ts
import { AccesTime, NotFoundError, RateLimitError, QuotaExceededError } from '@accestime/api-client'

try {
  await client.employees.get(999_999)
} catch (e) {
  if (e instanceof NotFoundError) console.log('no existe')
  else if (e instanceof RateLimitError) console.log(`esperar ${e.retryAfter}s`)
  else if (e instanceof QuotaExceededError) console.log('cuota mensual agotada')
  else throw e
}
```

## Reintentos automáticos

Default: 3 reintentos con backoff exponencial ante 408, 429 (rate limit), 5xx
y errores de red. Respeta `Retry-After`. El 429 por cuota mensual no se
reintenta.

```ts
const client = new AccesTime({ tenant: 'acme', apiKey: '...', maxRetries: 5 })
```

## Bulk

```ts
await client.marcados.createBulk(
  Array.from({ length: 1000 }, (_, i) => ({
    employee_id: 1,
    tipo_marcado_id: 1,
    local_id: 1,
    latitud: -34.6,
    longitud: -58.4,
    hora_evento: new Date(Date.now() - i * 86400000).toISOString(),
  })),
  { suppressWebhooks: true }  // útil para backfill
)
```

## Idempotency

Los métodos POST/PATCH añaden automáticamente un `Idempotency-Key` (UUID v4).
Para reintentos seguros, pasalo explícito:

```ts
await client.marcados.create({
  employee_id: 1, tipo_marcado_id: 1, local_id: 1,
  latitud: -34.6, longitud: -58.4,
  idempotency_key: 'sync-batch-2026-06-01-emp-1',
})
```

## Verificar firma de webhooks

```ts
import { verifyWebhookSignature, InvalidSignature } from '@accestime/api-client/webhooks'

app.post(
  '/accestime-webhook',
  express.raw({ type: 'application/json' }),
  (req, res) => {
    try {
      verifyWebhookSignature({
        secret: process.env.WEBHOOK_SECRET!,
        body: req.body,  // Buffer crudo, NO parsear antes
        signature: req.header('X-AccesTime-Signature')!,
        timestamp: parseInt(req.header('X-AccesTime-Timestamp')!, 10),
      })
    } catch (e) {
      if (e instanceof InvalidSignature) return res.status(401).send('bad signature')
      throw e
    }
    const event = JSON.parse(req.body.toString('utf-8'))
    // ... procesá el evento
    res.sendStatus(200)
  }
)
```

## Documentación

- API completa: https://docs.accestime.com
- Swagger UI: https://api.accestime.com/swagger

## Licencia

MIT

import { AccesTime, NotFoundError } from '../dist/index.js'
import { verifyWebhookSignature, InvalidSignature } from '../dist/webhooks.js'
import { createHmac, randomUUID } from 'node:crypto'

const TOKEN = process.env.SDK_TOKEN
if (!TOKEN) { console.error('SDK_TOKEN required'); process.exit(1) }

// El SDK por default hace fetch a https://demo.accestime.com/api/v1
// Para el smoke usamos un fetch wrapper que apunta a localhost:8001 (puerto expuesto del container)
// con Host header demo.accestime.com.
const wrappedFetch = (url, opts) => {
  const u = new URL(url)
  // Bypass nginx: en prod nginx strippea /api/ del tenant.{domain}/api/v1/* → /v1/*
  // Acá replicamos manual ese rewrite.
  const path = u.pathname.replace(/^\/api/, '')
  const newUrl = `http://localhost:8001${path}${u.search}`
  // undici strippea el Host header. Para el bypass usamos X-Tenant-Schema, que
  // el backend resuelve como fallback para tests internos. En prod NO se necesita.
  const headers = { ...(opts?.headers || {}), 'X-Tenant-Schema': 'demo' }
  return fetch(newUrl, { ...opts, headers })
}

const client = new AccesTime({
  tenant: 'demo',
  apiKey: TOKEN,
  fetch: wrappedFetch,
})

console.log('=== 1. list employees con paginación ===')
const p = await client.employees.list({ limit: 2 })
console.log(`  recibidos: ${p.data.length}  has_more=${p.pagination.has_more}`)

console.log('=== 2. iter all employees ===')
let total = 0
for await (const _ of client.employees.iter({ limit: 2 })) total++
console.log(`  total: ${total}`)

console.log('=== 3. GET single + NotFoundError ===')
const emp = await client.employees.get(1)
console.log(`  emp 1: ${emp.nombres} ${emp.apellidos}`)
try { await client.employees.get(999999) }
catch (e) {
  if (e instanceof NotFoundError) console.log(`  NotFoundError: ${e.detail}`)
  else { console.error('  ❌ wrong error', e); process.exit(1) }
}

console.log('=== 4. POST marcado (idem auto) ===')
const m1 = await client.marcados.create({
  employee_id: 1, tipo_marcado_id: 1, local_id: 1, latitud: -34.6, longitud: -58.4,
})
console.log(`  creado id=${m1.id}`)

console.log('=== 5. POST idem explícito ===')
const idem = `js-test-${randomUUID()}`
const m2 = await client.marcados.create({ employee_id: 1, tipo_marcado_id: 2, local_id: 1, latitud: -34.6, longitud: -58.4, idempotency_key: idem })
const m3 = await client.marcados.create({ employee_id: 1, tipo_marcado_id: 2, local_id: 1, latitud: -34.6, longitud: -58.4, idempotency_key: idem })
console.log(`  m2.id=${m2.id}  m3.id=${m3.id}  mismo? ${m2.id === m3.id}`)

console.log('=== 6. verifyWebhookSignature ===')
const secret = 'whsec_test_test_test_test_test'
const body = Buffer.from('{"event":"test"}')
const ts = Math.floor(Date.now() / 1000)
const sig = 'sha256=' + createHmac('sha256', secret).update(`${ts}.`).update(body).digest('hex')
verifyWebhookSignature({ secret, body, signature: sig, timestamp: ts })
console.log('  firma válida: OK')
try {
  verifyWebhookSignature({ secret, body: Buffer.concat([body, Buffer.from('X')]), signature: sig, timestamp: ts })
} catch (e) {
  if (e instanceof InvalidSignature) console.log(`  firma alterada → InvalidSignature: ${e.message}`)
  else { console.error('  ❌ wrong error', e); process.exit(1) }
}

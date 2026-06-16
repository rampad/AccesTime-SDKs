/**
 * @accestime/api-client — SDK oficial para la API de AccesTime.
 *
 * @example
 * ```ts
 * import { AccesTime } from '@accestime/api-client'
 *
 * const client = new AccesTime({ tenant: 'acme', apiKey: 'at_live_xxx' })
 *
 * for await (const emp of client.employees.iter({ limit: 100 })) {
 *   console.log(emp.nombres)
 * }
 *
 * await client.marcados.create({
 *   employee_id: 1, tipo_marcado_id: 1, local_id: 1,
 *   latitud: -34.6, longitud: -58.4,
 * })
 * ```
 */
import { fromResponse, AccesTimeError, QuotaExceededError } from './errors.js'

export * from './errors.js'
export { verifyWebhookSignature, InvalidSignature } from './webhooks.js'

const DEFAULT_TIMEOUT_MS = 30_000
const DEFAULT_MAX_RETRIES = 3
const RETRYABLE_STATUS = new Set([408, 429, 500, 502, 503, 504])
const USER_AGENT = 'accestime-js/0.1.0'

export interface ClientOptions {
  tenant?: string
  apiKey?: string
  baseUrl?: string
  timeoutMs?: number
  maxRetries?: number
  fetch?: typeof globalThis.fetch
}

interface RequestOptions {
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  path: string
  params?: Record<string, unknown>
  body?: unknown
  idempotencyKey?: string
}

interface PaginatedResponse<T> {
  data: T[]
  pagination: { next_cursor: string | null; has_more: boolean }
}

function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  // Fallback
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

function buildQuery(params?: Record<string, unknown>): string {
  if (!params) return ''
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue
    usp.append(k, String(v))
  }
  const s = usp.toString()
  return s ? `?${s}` : ''
}

export class AccesTime {
  readonly tenant: string
  readonly baseUrl: string
  readonly maxRetries: number
  private readonly headers: Record<string, string>
  private readonly timeoutMs: number
  private readonly fetchImpl: typeof globalThis.fetch

  readonly employees: Employees
  readonly marcados: Marcados
  readonly jornadas: Jornadas
  readonly turnos: Turnos
  readonly webhooks: Webhooks

  constructor(opts: ClientOptions = {}) {
    const tenant = opts.tenant ?? (typeof process !== 'undefined' ? process.env?.ACCESTIME_TENANT : undefined)
    const apiKey = opts.apiKey ?? (typeof process !== 'undefined' ? process.env?.ACCESTIME_API_KEY : undefined)
    if (!tenant) throw new Error('tenant es requerido (opt o env ACCESTIME_TENANT)')
    if (!apiKey) throw new Error('apiKey es requerido (opt o env ACCESTIME_API_KEY)')
    this.tenant = tenant
    this.baseUrl = opts.baseUrl ?? `https://${tenant}.accestime.com/api/v1`
    this.maxRetries = opts.maxRetries ?? DEFAULT_MAX_RETRIES
    this.timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS
    this.fetchImpl = opts.fetch ?? globalThis.fetch
    this.headers = {
      Authorization: `Bearer ${apiKey}`,
      'User-Agent': USER_AGENT,
      Accept: 'application/json',
    }

    const req = this.request.bind(this)
    this.employees = new Employees(req)
    this.marcados = new Marcados(req)
    this.jornadas = new Jornadas(req)
    this.turnos = new Turnos(req)
    this.webhooks = new Webhooks(req)
  }

  async request<T = unknown>(opts: RequestOptions): Promise<T | null> {
    const url = `${this.baseUrl}${opts.path}${buildQuery(opts.params)}`
    const headers: Record<string, string> = { ...this.headers }
    let idemKey = opts.idempotencyKey
    if (idemKey == null && (opts.method === 'POST' || opts.method === 'PATCH')) {
      idemKey = uuid()
    }
    if (idemKey) headers['Idempotency-Key'] = idemKey
    const bodyStr = opts.body != null ? JSON.stringify(opts.body) : undefined
    if (bodyStr != null) headers['Content-Type'] = 'application/json'

    let lastErr: unknown
    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      const ac = new AbortController()
      const tid = setTimeout(() => ac.abort(), this.timeoutMs)
      let res: Response
      try {
        res = await this.fetchImpl(url, { method: opts.method, headers, body: bodyStr, signal: ac.signal })
      } catch (e) {
        clearTimeout(tid)
        lastErr = e
        if (attempt >= this.maxRetries) throw e
        await sleep(backoff(attempt))
        continue
      }
      clearTimeout(tid)

      if (res.status < 400) {
        if (res.status === 204) return null
        const text = await res.text()
        return text ? (JSON.parse(text) as T) : null
      }

      const text = await res.text()

      if (RETRYABLE_STATUS.has(res.status) && attempt < this.maxRetries) {
        // 429 por cuota mensual NO se reintenta (no va a desbloquearse hasta el mes siguiente)
        if (res.status === 429 && text.includes('Cuota')) {
          throw fromResponse(res.status, text, res.headers)
        }
        const ra = res.headers.get('retry-after')
        const wait = ra && /^\d+$/.test(ra) ? parseInt(ra, 10) * 1000 : backoff(attempt)
        await sleep(wait)
        continue
      }
      throw fromResponse(res.status, text, res.headers)
    }

    if (lastErr) throw lastErr
    throw new AccesTimeError(0, 'Max retries exhausted', '')
  }
}

function backoff(attempt: number): number {
  return Math.min(2 ** attempt * 500, 30_000)
}
function sleep(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms))
}

// ── Resources ───────────────────────────────────────────────────────────────

type RequestFn = <T = unknown>(opts: RequestOptions) => Promise<T | null>

abstract class PaginatedResource<T = Record<string, unknown>> {
  protected req: RequestFn
  protected abstract path: string
  constructor(req: RequestFn) { this.req = req }

  protected async _list(params?: Record<string, unknown>): Promise<PaginatedResponse<T>> {
    return (await this.req<PaginatedResponse<T>>({ method: 'GET', path: this.path, params }))!
  }

  async *iter(params?: Record<string, unknown>): AsyncGenerator<T> {
    let cursor: string | null = null
    do {
      const page: PaginatedResponse<T> = await this._list({ ...params, ...(cursor ? { cursor } : {}) })
      for (const item of page.data) yield item
      cursor = page.pagination.has_more ? page.pagination.next_cursor : null
    } while (cursor)
  }
}

export interface EmployeeListParams {
  limit?: number; cursor?: string
  status?: 'active' | 'inactive' | 'suspended'
  local_id?: number; updated_since?: string
}

export class Employees extends PaginatedResource {
  protected path = '/employees'
  list(p: EmployeeListParams = {}) { return this._list(p as Record<string, unknown>) }
  get(id: number) { return this.req({ method: 'GET', path: `${this.path}/${id}` }) }
  create(body: Record<string, unknown> & { idempotency_key?: string }) {
    const { idempotency_key, ...rest } = body
    return this.req({ method: 'POST', path: this.path, body: rest, idempotencyKey: idempotency_key })
  }
  createBulk(employees: Record<string, unknown>[], opts: { suppressWebhooks?: boolean; idempotencyKey?: string } = {}) {
    return this.req({ method: 'POST', path: `${this.path}:bulk`,
      body: { employees, suppress_webhooks: !!opts.suppressWebhooks },
      idempotencyKey: opts.idempotencyKey })
  }
  update(id: number, body: Record<string, unknown> & { idempotency_key?: string }) {
    const { idempotency_key, ...rest } = body
    return this.req({ method: 'PATCH', path: `${this.path}/${id}`, body: rest, idempotencyKey: idempotency_key })
  }
}

export interface MarcadoListParams {
  desde: string; hasta: string
  limit?: number; cursor?: string
  employee_id?: number; local_id?: number
  tipo_registro?: 'local' | 'mobil' | 'web' | 'api' | 'qr'
}

export class Marcados extends PaginatedResource {
  protected path = '/marcados'
  list(p: MarcadoListParams) { return this._list(p as unknown as Record<string, unknown>) }
  create(body: Record<string, unknown> & { idempotency_key?: string }) {
    const { idempotency_key, ...rest } = body
    return this.req({ method: 'POST', path: this.path, body: rest, idempotencyKey: idempotency_key })
  }
  createBulk(marcados: Record<string, unknown>[], opts: { suppressWebhooks?: boolean; idempotencyKey?: string } = {}) {
    return this.req({ method: 'POST', path: `${this.path}:bulk`,
      body: { marcados, suppress_webhooks: !!opts.suppressWebhooks },
      idempotencyKey: opts.idempotencyKey })
  }
}

export interface JornadaListParams {
  desde: string; hasta: string
  limit?: number; cursor?: string
  employee_id?: number; local_id?: number
  estado?: 'en_curso' | 'completada' | 'incompleta'
}

export class Jornadas extends PaginatedResource {
  protected path = '/jornadas'
  list(p: JornadaListParams) { return this._list(p as unknown as Record<string, unknown>) }
}

export interface TurnoListParams {
  limit?: number; cursor?: string; local_id?: number; activo?: boolean
}

export class Turnos extends PaginatedResource {
  protected path = '/turnos'
  list(p: TurnoListParams = {}) { return this._list(p as unknown as Record<string, unknown>) }
}

export class Webhooks {
  private req: RequestFn
  private path = '/webhooks'
  constructor(req: RequestFn) { this.req = req }

  list(opts: { includeRevoked?: boolean } = {}) {
    return this.req({ method: 'GET', path: this.path, params: { include_revoked: !!opts.includeRevoked } })
  }
  create(body: { name: string; url: string; events: string[] }) {
    return this.req({ method: 'POST', path: this.path, body })
  }
  delete(id: number) {
    return this.req({ method: 'DELETE', path: `${this.path}/${id}` })
  }
  deliveries(id: number, params: { limit?: number; cursor?: string; status?: string } = {}) {
    return this.req({ method: 'GET', path: `${this.path}/${id}/deliveries`, params })
  }
}

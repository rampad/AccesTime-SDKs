/**
 * Excepciones tipadas. Mirá `from_response` para el mapeo de status → tipo.
 */

export class AccesTimeError extends Error {
  status: number
  detail: unknown
  responseBody: string

  constructor(status: number, detail: unknown, responseBody: string) {
    super(`HTTP ${status}: ${typeof detail === 'string' ? detail : responseBody.slice(0, 200)}`)
    this.name = 'AccesTimeError'
    this.status = status
    this.detail = detail
    this.responseBody = responseBody
  }
}

export class BadRequestError extends AccesTimeError { constructor(s: number, d: unknown, b: string) { super(s, d, b); this.name = 'BadRequestError' } }
export class AuthError extends AccesTimeError { constructor(s: number, d: unknown, b: string) { super(s, d, b); this.name = 'AuthError' } }
export class ForbiddenError extends AccesTimeError { constructor(s: number, d: unknown, b: string) { super(s, d, b); this.name = 'ForbiddenError' } }
export class NotFoundError extends AccesTimeError { constructor(s: number, d: unknown, b: string) { super(s, d, b); this.name = 'NotFoundError' } }
export class ConflictError extends AccesTimeError { constructor(s: number, d: unknown, b: string) { super(s, d, b); this.name = 'ConflictError' } }
export class ValidationError extends AccesTimeError { constructor(s: number, d: unknown, b: string) { super(s, d, b); this.name = 'ValidationError' } }
export class ServerError extends AccesTimeError { constructor(s: number, d: unknown, b: string) { super(s, d, b); this.name = 'ServerError' } }

export class RateLimitError extends AccesTimeError {
  retryAfter: number | null
  constructor(s: number, d: unknown, b: string, retryAfter: number | null = null) {
    super(s, d, b); this.name = 'RateLimitError'; this.retryAfter = retryAfter
  }
}

export class QuotaExceededError extends AccesTimeError {
  constructor(s: number, d: unknown, b: string) { super(s, d, b); this.name = 'QuotaExceededError' }
}

export function fromResponse(status: number, bodyText: string, headers: Headers): AccesTimeError {
  let detail: unknown
  try { detail = JSON.parse(bodyText)?.detail } catch { /* */ }

  if (status === 400) return new BadRequestError(status, detail, bodyText)
  if (status === 401) return new AuthError(status, detail, bodyText)
  if (status === 403) return new ForbiddenError(status, detail, bodyText)
  if (status === 404) return new NotFoundError(status, detail, bodyText)
  if (status === 409) return new ConflictError(status, detail, bodyText)
  if (status === 422) return new ValidationError(status, detail, bodyText)
  if (status === 429) {
    if (typeof detail === 'string' && detail.includes('Cuota')) {
      return new QuotaExceededError(status, detail, bodyText)
    }
    const ra = headers.get('retry-after')
    return new RateLimitError(status, detail, bodyText, ra ? parseInt(ra, 10) : null)
  }
  if (status >= 500 && status < 600) return new ServerError(status, detail, bodyText)
  return new AccesTimeError(status, detail, bodyText)
}

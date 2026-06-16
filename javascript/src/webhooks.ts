/**
 * Helpers para verificar firmas de webhooks del lado del receptor.
 *
 * @example
 * ```ts
 * import { verifyWebhookSignature } from '@accestime/api-client/webhooks'
 *
 * app.post('/accestime-webhook', express.raw({type:'application/json'}), (req, res) => {
 *   try {
 *     verifyWebhookSignature({
 *       secret: process.env.WEBHOOK_SECRET!,
 *       body: req.body,  // Buffer
 *       signature: req.header('X-AccesTime-Signature')!,
 *       timestamp: parseInt(req.header('X-AccesTime-Timestamp')!, 10),
 *     })
 *   } catch {
 *     return res.status(401).send('bad signature')
 *   }
 *   // ...
 * })
 * ```
 */
import { createHmac, timingSafeEqual } from 'node:crypto'

const REPLAY_WINDOW_SECONDS = 300

export class InvalidSignature extends Error {
  constructor(msg: string) { super(msg); this.name = 'InvalidSignature' }
}

export interface VerifyOpts {
  secret: string
  body: Buffer | string | Uint8Array
  signature: string
  timestamp: number
  toleranceSeconds?: number
}

export function verifyWebhookSignature(opts: VerifyOpts): void {
  const now = Math.floor(Date.now() / 1000)
  const tol = opts.toleranceSeconds ?? REPLAY_WINDOW_SECONDS
  if (Math.abs(now - opts.timestamp) > tol) {
    throw new InvalidSignature(`Timestamp ${opts.timestamp} fuera de la ventana de ${tol}s`)
  }

  const bodyBuf = typeof opts.body === 'string' ? Buffer.from(opts.body)
                : opts.body instanceof Buffer ? opts.body
                : Buffer.from(opts.body)

  const expected = 'sha256=' + createHmac('sha256', opts.secret)
    .update(`${opts.timestamp}.`)
    .update(bodyBuf)
    .digest('hex')

  const a = Buffer.from(opts.signature ?? '')
  const b = Buffer.from(expected)
  if (a.length !== b.length || !timingSafeEqual(a, b)) {
    throw new InvalidSignature('Firma HMAC no coincide')
  }
}

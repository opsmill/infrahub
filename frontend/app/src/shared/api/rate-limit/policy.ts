// Retry policy for HTTP 429 responses.
//
// The API sheds load with `429 Too Many Requests` + `Retry-After`, and a shed
// request never reached a handler, so replaying one repeats no work. The
// advised wait is adaptive and escalates under sustained load, up to 30s
// (`dev/adr/0007-adaptive-retry-after-under-load.md`).
//
// Every decision here is a pure function; only the driver touches a clock.

import { HTTP_TOO_MANY_REQUESTS } from "@/shared/api/rate-limit/shed-envelope";

/** Attempts after the initial one. */
export const MAX_RETRIES = 3;

// Backoff bounds, used only when a 429 arrives without an advised wait.
const BACKOFF_BASE_MS = 300;
const BACKOFF_CEILING_MS = 10_000;

// Bounds the wait for someone watching a page: the advice can escalate to 30s,
// and holding a spinner that long is worse than surfacing an error they can act on.
const TOTAL_RETRY_WINDOW_MS = 15_000;

// A page load's requests are shed in the same instant, so without a spread they
// would all come back on the same millisecond.
const HERD_JITTER_MS = 500;

/**
 * The `Retry-After` wait in milliseconds, or `null` when the header is absent
 * or unparseable. Handles both RFC 7231 forms (delta-seconds and HTTP-date); a
 * date already in the past floors to 0.
 */
export function parseRetryAfter(
  header: string | null | undefined,
  now: number = Date.now()
): number | null {
  const value = header?.trim();
  if (!value) return null;

  if (/^\d+$/.test(value)) {
    const seconds = Number(value);
    return Number.isFinite(seconds) ? seconds * 1000 : null;
  }

  // All three RFC 7231 date forms start with a weekday name; requiring one stops
  // `Date.parse`'s permissive fallback from reading junk as a date (V8 resolves
  // "-5" to a day in 2001).
  if (!/^(mon|tue|wed|thu|fri|sat|sun)/i.test(value)) return null;

  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return null;
  return Math.max(0, parsed - now);
}

function computeBackoffMs(attempt: number): number {
  // The exponent is capped so raising MAX_RETRIES can never overflow before the
  // clamp applies.
  return Math.min(BACKOFF_CEILING_MS, BACKOFF_BASE_MS * 2 ** Math.min(attempt, 30));
}

/**
 * How long to wait before the next attempt: the server's advice when it gave
 * any, otherwise a full-jitter exponential backoff.
 *
 * An advised wait is a floor and never a ceiling — jitter is added on top, so a
 * retry never lands earlier than the server said it could.
 */
export function nextDelayMs(
  attempt: number,
  retryAfterHeader: string | null | undefined,
  random: () => number = Math.random
): number {
  const advised = parseRetryAfter(retryAfterHeader);
  if (advised !== null) return advised + random() * HERD_JITTER_MS;
  return random() * computeBackoffMs(attempt);
}

function sleep(ms: number, signal?: AbortSignal | null): Promise<void> {
  if (ms <= 0) return Promise.resolve();

  return new Promise((resolve) => {
    const finish = () => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", finish);
      resolve();
    };
    const timer = setTimeout(finish, ms);
    signal?.addEventListener("abort", finish, { once: true });
  });
}

export type RateLimitRetryOptions = {
  /** Cuts a wait short; an aborted request is never replayed. */
  signal?: AbortSignal | null;
  /** Whether this particular 429 may be replayed at all. */
  canReplay?: (response: Response) => boolean | Promise<boolean>;
  /** Seams so the arithmetic can be driven deterministically in tests. */
  random?: () => number;
  now?: () => number;
};

/**
 * Call `send` until it returns something other than a 429, the retry budget
 * runs out, or the next advised wait would run past the retry window.
 *
 * `send` performs one HTTP send per call and must yield a readable body each
 * time, since it is re-invoked per attempt. Never throws on exhaustion: the
 * last response is returned as-is, so a 429 that outlives the budget stays an
 * ordinary 429 for the layers above.
 */
export async function sendWithRateLimitRetry(
  send: () => Promise<Response>,
  options: RateLimitRetryOptions = {}
): Promise<Response> {
  const { signal, canReplay, random = Math.random, now = Date.now } = options;
  const deadline = now() + TOTAL_RETRY_WINDOW_MS;

  let attempts = 0;
  for (;;) {
    const response = await send();
    attempts += 1;

    if (response.status !== HTTP_TOO_MANY_REQUESTS) return response;
    if (attempts > MAX_RETRIES || signal?.aborted) return response;
    if (canReplay && !(await canReplay(response))) return response;

    const delay = nextDelayMs(attempts - 1, response.headers.get("Retry-After"), random);
    if (now() + delay > deadline) return response;

    await sleep(delay, signal);
    if (signal?.aborted) return response;
  }
}

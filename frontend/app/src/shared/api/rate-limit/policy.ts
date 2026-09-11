// Retry policy for HTTP 429 responses.
//
// The API sheds load with `429 Too Many Requests` + `Retry-After`, and a shed
// request never reached a handler, so replaying one repeats no work. The
// advised wait is adaptive and escalates under sustained load, up to 30s.
//
// The header parser and the delay computation take their clock and random
// source as parameters that default to the real ones, so a test can pin them;
// the driver reads the real clock for its retry window and waits on real
// timers.

import { HTTP_TOO_MANY_REQUESTS } from "@/shared/api/rate-limit/shed-envelope";
import { waitFor } from "@/shared/utils/common";

/** Attempts after the initial one. */
export const MAX_RETRIES = 3;

// Backoff bounds. The ceiling also clamps an advised wait, as the SDK's
// `backoff_max` does: a 20s or 30s escalated hint would otherwise never fit
// the window below, and the UI would give up on the first 429 exactly when the
// server is most overloaded.
const BACKOFF_BASE_MS = 300;
const BACKOFF_CEILING_MS = 10_000;

// Bounds the wait for someone watching a page: holding a spinner for the
// server's full escalated advice is worse than surfacing an error they can act on.
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
  // `2 ** attempt` saturates to Infinity rather than overflowing, and Math.min
  // clamps that, so no exponent cap is needed.
  return Math.min(BACKOFF_CEILING_MS, BACKOFF_BASE_MS * 2 ** attempt);
}

/**
 * How long to wait before the next attempt: the server's advice when it gave
 * any, otherwise a full-jitter exponential backoff.
 *
 * An advised wait is honored up to the backoff ceiling and clamped above it,
 * the rule the SDK applies too. Jitter is added on top either way, so a burst
 * of requests shed together does not come back together.
 */
export function nextDelayMs(
  attempt: number,
  retryAfterHeader: string | null | undefined,
  random: () => number = Math.random
): number {
  const advised = parseRetryAfter(retryAfterHeader);
  if (advised !== null) {
    return Math.min(advised, BACKOFF_CEILING_MS) + random() * HERD_JITTER_MS;
  }
  return random() * computeBackoffMs(attempt);
}

/** A replay the driver has decided on: which retry it is and how long it waits first. */
export type ScheduledRetry = { attempt: number; delayMs: number };

/** How a scheduled wait ended: the replay was sent, or the caller aborted first. */
export type RetryOutcome = "replayed" | "abandoned";

export type RateLimitRetryOptions = {
  /**
   * Cuts a wait short. An aborted request is never replayed: the call rejects
   * with the signal's reason, as `fetch` itself does.
   */
  signal?: AbortSignal | null;
  /** Whether this particular 429 may be replayed at all. */
  canReplay?: (response: Response) => boolean;
  /** Seam so the jitter can be driven deterministically in tests. */
  random?: () => number;
  /**
   * Told about each replay just before the wait for it starts. May return a
   * callback, which is then told how the wait ended, so a notice about the
   * replay can be withdrawn if it is never sent.
   */
  onRetryScheduled?: (retry: ScheduledRetry) => ((outcome: RetryOutcome) => void) | undefined;
};

/**
 * Call `send` until it returns something other than a 429, the retry budget
 * runs out, or the next wait would run past the retry window.
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
  const { signal, canReplay, random = Math.random, onRetryScheduled } = options;
  const deadline = Date.now() + TOTAL_RETRY_WINDOW_MS;

  for (let attempt = 0; ; attempt += 1) {
    const response = await send();
    if (response.status !== HTTP_TOO_MANY_REQUESTS || attempt >= MAX_RETRIES) return response;
    if (canReplay && !canReplay(response)) return response;

    const delay = nextDelayMs(attempt, response.headers.get("Retry-After"), random);
    if (Date.now() + delay > deadline) return response;

    const settle = onRetryScheduled?.({ attempt, delayMs: delay });
    await waitFor(delay, signal);
    settle?.(signal?.aborted ? "abandoned" : "replayed");
    // Aborted before or during the wait: reject as `fetch` would, rather than
    // hand back a 429 for a request the caller has abandoned.
    signal?.throwIfAborted();
  }
}

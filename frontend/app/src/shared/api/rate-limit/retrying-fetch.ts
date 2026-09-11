import { sendWithRateLimitRetry } from "@/shared/api/rate-limit/policy";
import { notifyRetryScheduled } from "@/shared/api/rate-limit/retry-notice";
import { isShedResponse } from "@/shared/api/rate-limit/shed-envelope";

// Replaying these is safe whoever returned the 429.
const IDEMPOTENT_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

// Anything else is replayed only against Infrahub's own shed, whose marker
// proves the request never reached a handler; a 429 from something else in
// front of the API could mean the write landed.
const canReplay = (method: string, response: Response): boolean =>
  IDEMPOTENT_METHODS.has(method) || isShedResponse(response);

/**
 * `fetch` with the 429 retry policy applied.
 *
 * The seam every transport shares, so load shedding is handled once — below the
 * auth layer, and below the query cache where `Retry-After` is still readable.
 */
export const retryingFetch: typeof fetch = (input, init) => {
  const request = input instanceof Request ? input : null;
  // `init` overrides the Request's own fields, as it does for `fetch` itself:
  // an explicit `signal: null` clears the Request's signal rather than
  // falling back to it.
  const method = (init?.method ?? request?.method ?? "GET").toUpperCase();
  const signal = init?.signal === undefined ? request?.signal : init.signal;

  return sendWithRateLimitRetry(
    // A Request body is single-use, so every attempt sends its own clone and the
    // original stays intact for whoever else holds it. A url + init pair is
    // re-sent as-is, which holds because those bodies are strings — a stream
    // body could not be replayed.
    () => fetch(request ? request.clone() : input, init),
    {
      signal,
      canReplay: (response) => canReplay(method, response),
      onRetryScheduled: (retry) => notifyRetryScheduled(retry.delayMs),
    }
  );
};

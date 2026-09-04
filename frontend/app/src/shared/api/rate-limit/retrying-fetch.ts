import { sendWithRateLimitRetry } from "@/shared/api/rate-limit/policy";
import { isShedResponse } from "@/shared/api/rate-limit/shed-envelope";

// Replaying these is safe whoever returned the 429.
const IDEMPOTENT_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

function canReplay(method: string, response: Response): boolean | Promise<boolean> {
  if (IDEMPOTENT_METHODS.has(method)) return true;

  // Only Infrahub's own shed guarantees the request never reached a handler; a
  // 429 from something else in front of the API could mean the write landed.
  return isShedResponse(response);
}

/**
 * `fetch` with the 429 retry policy applied.
 *
 * The seam every transport shares, so load shedding is handled once — below the
 * auth layer, and below the query cache where `Retry-After` is still readable.
 */
export const retryingFetch: typeof fetch = (input, init) => {
  const request = input instanceof Request ? input : null;
  const method = (request?.method ?? init?.method ?? "GET").toUpperCase();
  const signal = request?.signal ?? init?.signal;

  return sendWithRateLimitRetry(
    // A Request body is single-use, so every attempt sends its own clone and the
    // original stays intact for whoever else holds it. The other path re-sends
    // `init` as-is, which holds because those bodies are strings — a stream body
    // could not be replayed.
    () => (request ? fetch(request.clone(), init) : fetch(input, init)),
    { signal, canReplay: (response) => canReplay(method, response) }
  );
};

import {
  HTTP_TOO_MANY_REQUESTS,
  SHED_MARKER_HEADER,
  SHED_MARKER_VALUE,
} from "../../src/shared/api/rate-limit/shed-envelope";

/** The server's own wording on a shed; the UI replaces it with `SHED_USER_MESSAGE`. */
export const SHED_MESSAGE = "Server is shedding load; retry later.";

/** The envelope the API answers a shed request with, on both the REST and the GraphQL surface. */
export const SHED_BODY = {
  data: null,
  errors: [{ message: SHED_MESSAGE, extensions: { code: HTTP_TOO_MANY_REQUESTS } }],
};

export const jsonResponse = (
  body: unknown,
  status = 200,
  headers: Record<string, string> = {}
): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });

/** A 429 written by Infrahub's admission layer: the shed marker plus the envelope. */
export const shedResponse = (headers: Record<string, string> = {}): Response =>
  jsonResponse(SHED_BODY, HTTP_TOO_MANY_REQUESTS, {
    [SHED_MARKER_HEADER]: SHED_MARKER_VALUE,
    ...headers,
  });

/** A 429 from an ingress, CDN or gateway in front of the API: no marker, foreign body. */
export const foreignRateLimitResponse = (): Response =>
  jsonResponse({ detail: "slow down" }, HTTP_TOO_MANY_REQUESTS);

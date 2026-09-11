// The API's load-shed contract.
//
// A shed request is answered before the app runs, so there is no exception to
// map through the error catalogue: `extensions.code` is the integer HTTP status
// rather than a catalogue identifier, on both the REST and the GraphQL surface,
// and the response is marked with a header only the admission layer sets.

export const HTTP_TOO_MANY_REQUESTS = 429;

// The marker is what proves a 429 came from the shed and never reached a
// handler. The body cannot: the REST exception handler emits the same
// integer-code envelope for any error, so its shape alone could one day
// describe a write that did land. Cross-origin, the header is readable because
// the server's CORS middleware exposes it.
export const SHED_MARKER_HEADER = "X-Infrahub-Admission";
export const SHED_MARKER_VALUE = "shed";

// The server's own message describes the mechanism ("shedding load"); this one
// describes what the person in front of the screen should do about it.
export const SHED_USER_MESSAGE =
  "Infrahub is busy and could not process this request. Please try again in a moment.";

/** Whether a GraphQL `extensions` blob is a shed rather than a catalogue error. */
export function isShedErrorItem(extensions: unknown): boolean {
  if (extensions === null || typeof extensions !== "object") return false;
  // Strict on the integer: a catalogue error carries a string code, and
  // conflating the two is what routes a shed into the unknown-code fallback.
  return (extensions as { code?: unknown }).code === HTTP_TOO_MANY_REQUESTS;
}

/**
 * Whether this 429 is an Infrahub admission shed rather than one from an
 * ingress, CDN or gateway in front of the API. Reads only headers, so the body
 * stays untouched for the caller.
 */
export function isShedResponse(response: Response): boolean {
  return (
    response.status === HTTP_TOO_MANY_REQUESTS &&
    response.headers.get(SHED_MARKER_HEADER) === SHED_MARKER_VALUE
  );
}

// The API's load-shed envelope.
//
// A shed request is answered before the app runs, so there is no exception to
// map through the error catalogue: `extensions.code` is the integer HTTP status
// rather than a catalogue identifier string, on both the REST and the GraphQL
// surface.

export const HTTP_TOO_MANY_REQUESTS = 429;

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

function hasShedEnvelope(body: unknown): boolean {
  if (body === null || typeof body !== "object") return false;
  const { errors } = body as { errors?: unknown };
  if (!Array.isArray(errors)) return false;
  return errors.some((item) => isShedErrorItem((item as { extensions?: unknown })?.extensions));
}

/**
 * Whether this 429 is an Infrahub admission shed rather than one from an
 * ingress, CDN or gateway in front of the API. Only the former guarantees the
 * request never reached a handler. Leaves the response body readable.
 */
export async function isShedResponse(response: Response): Promise<boolean> {
  if (response.status !== HTTP_TOO_MANY_REQUESTS) return false;

  try {
    return hasShedEnvelope(await response.clone().json());
  } catch {
    // Not JSON, or the body is already gone: treat it as a foreign 429.
    return false;
  }
}

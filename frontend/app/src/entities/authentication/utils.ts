import type { Location, Path } from "react-router";

import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from "@/entities/authentication/constants";
import type { UserToken } from "@/entities/authentication/types";

// Validates that `raw` is a path-absolute, same-origin reference and
// returns it as a Partial<Path>. Rejects protocol-relative (`//evil`),
// schemed (`https://evil`), and anything URL() can't parse. Used by the
// login flow to guard the `?from=` redirect target against open-redirect
// abuse — the value comes from a URL query param, so it is attacker-controlled.
//
// Note on the post-normalization pathname check: WHATWG URL parsing
// collapses `..` segments, so `/..//evil.com` resolves to pathname
// `//evil.com` against the same origin. Origin-equality alone would
// pass that through, and the returned protocol-relative pathname then
// becomes the open-redirect payload when the caller serialises it back
// to a string (Navigate to / SSO `final_url=…`). Reject any pathname
// that starts with `//` after normalization, regardless of origin.
export const safeInternalPath = (raw: string | null | undefined): Partial<Path> | null => {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return null;
  try {
    const url = new URL(raw, window.location.origin);
    if (url.origin !== window.location.origin) return null;
    if (url.pathname.startsWith("//")) return null;
    return { pathname: url.pathname, search: url.search, hash: url.hash };
  } catch {
    return null;
  }
};

// Serialises a Partial<Path> back to a single path string for callers
// that need a string (e.g. building a `final_url=...` query param for
// the SSO authorize endpoint, where the backend expects a flat string).
export const pathToString = (path: Partial<Path>): string =>
  (path.pathname ?? "/") + (path.search ?? "") + (path.hash ?? "");

// Resolves the post-login redirect target by preferring in-app router
// state (set by ProtectedRoute) and falling back to the `?from=` query
// param (set by `redirectToLogin()` on hard nav). Both sources are
// revalidated through `safeInternalPath` so router-state pollution is
// held to the same open-redirect guard as the query-string twin.
// Defaults to "/" when neither source yields a safe target.
export const resolveLoginRedirect = (
  location: Pick<Location, "state">,
  searchParams: URLSearchParams
): Partial<Path> => {
  const stateFromRaw = (location.state as { from?: Partial<Path> } | null)?.from;
  const stateFrom = stateFromRaw ? safeInternalPath(pathToString(stateFromRaw)) : null;
  const queryFrom = safeInternalPath(searchParams.get("from"));
  return stateFrom ?? queryFrom ?? { pathname: "/" };
};

export const saveTokensInLocalStorage = (result: Partial<UserToken>) => {
  if (result?.access_token) {
    localStorage.setItem(ACCESS_TOKEN_KEY, result?.access_token);
  }

  if (result?.refresh_token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, result?.refresh_token);
  }
};

export const removeTokensInLocalStorage = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};

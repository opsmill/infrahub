import type { Path } from "react-router";

import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from "@/entities/authentication/constants";
import type { UserToken } from "@/entities/authentication/types";

// Validates that `raw` is a path-absolute, same-origin reference and
// returns it as a Partial<Path>. Rejects protocol-relative (`//evil`),
// schemed (`https://evil`), and anything URL() can't parse. Used by the
// login flow to guard the `?from=` redirect target against open-redirect
// abuse — the value comes from a URL query param, so it is attacker-controlled.
export const safeInternalPath = (raw: string | null | undefined): Partial<Path> | null => {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return null;
  try {
    const url = new URL(raw, window.location.origin);
    if (url.origin !== window.location.origin) return null;
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

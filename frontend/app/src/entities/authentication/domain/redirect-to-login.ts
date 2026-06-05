import { removeTokensInLocalStorage } from "@/entities/authentication/utils";

// Token is invalid or missing — clear local credentials and bounce to /login.
// Hard-navigates because callers (Apollo errorLink, REST middleware) run
// outside React Router, and the AuthProvider's state does not re-render on
// external storage writes. Skips the redirect if we're already on /login to
// avoid loops.
//
// Encodes the current path as `?from=…` so `LoginPage` can route the user
// back after re-authenticating. The hard nav means `location.state` is gone,
// so the query string is the only carrier left.

// Holder so tests can stub the hard-nav without touching `window.location`
// (which is non-configurable in real browsers — vitest's browser mode hits
// that wall the moment you try to spy on `assign`). Production reads
// through this same reference, so the indirection costs one property lookup.
export const __navigation = {
  assign: (url: string) => window.location.assign(url),
};

export function redirectToLogin(): void {
  removeTokensInLocalStorage();
  if (window.location.pathname === "/login") return;

  const from = window.location.pathname + window.location.search + window.location.hash;
  __navigation.assign(`/login?from=${encodeURIComponent(from)}`);
}

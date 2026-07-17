import type React from "react";

import { DatePreferencesContext } from "@/shared/context/date-preferences-context";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { resolveDatePreferences } from "@/entities/preferences/domain/rules/resolve-date-preferences";
import { useGetEffectivePreferences } from "@/entities/preferences/ui/queries/get-effective-preferences.query";

/**
 * Fills the shared {@link DatePreferencesContext} from the effective preferences. Lives in
 * `entities/preferences` (which owns the data) so `shared/DateDisplay` reads only the resolved
 * `{ pattern, timezone }` and never imports `entities`. A `DEFAULT` source (or no data yet) leaves
 * the field null, so consumers fall back to the browser locale/zone.
 *
 * Only fetches for an authenticated user. The effective-preferences query requires auth, but the
 * app also renders for logged-out users (`allow_anonymous_access`), where an ungated query would
 * 401 and Apollo's error link would bounce them to `/login`. Gating by *mount* (not react-query
 * `enabled`) keeps the query hook itself auth-agnostic — logged-out users just get the fallback.
 */
export function DatePreferencesProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) return children;

  return <AuthenticatedDatePreferences>{children}</AuthenticatedDatePreferences>;
}

function AuthenticatedDatePreferences({ children }: { children: React.ReactNode }) {
  const { data } = useGetEffectivePreferences();
  const resolved = resolveDatePreferences(data);

  return <DatePreferencesContext value={resolved}>{children}</DatePreferencesContext>;
}

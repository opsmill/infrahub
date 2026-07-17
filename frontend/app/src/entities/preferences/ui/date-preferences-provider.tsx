import React from "react";

import {
  DatePreferencesContext,
  type ResolvedDatePreferences,
} from "@/shared/context/date-preferences-context";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { patternForKey } from "@/entities/preferences/domain/rules/date-format";
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

  const resolved = React.useMemo<ResolvedDatePreferences>(() => {
    const dateFormat = data?.dateFormat;
    const timezone = data?.timezone;

    return {
      pattern:
        dateFormat && dateFormat.source !== "DEFAULT" && dateFormat.value
          ? patternForKey(dateFormat.value)
          : null,
      timezone: timezone && timezone.source !== "DEFAULT" ? (timezone.value ?? null) : null,
    };
  }, [data]);

  return <DatePreferencesContext value={resolved}>{children}</DatePreferencesContext>;
}

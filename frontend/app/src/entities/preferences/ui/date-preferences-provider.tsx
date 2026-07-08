import React from "react";

import {
  DatePreferencesContext,
  type ResolvedDatePreferences,
} from "@/shared/context/date-preferences-context";

import { patternForKey } from "@/entities/preferences/domain/rules/date-format";
import { useGetEffectivePreferences } from "@/entities/preferences/ui/queries/get-effective-preferences.query";

/**
 * Fills the shared {@link DatePreferencesContext} from the effective user/org preferences. This
 * lives in `entities/preferences` — NOT `shared` — because it is the layer that owns the
 * preferences data (`useEffectivePreferences`). `shared/DateDisplay` consumes only the resolved
 * `{ pattern, timezone }` via context, so it never imports `entities`.
 *
 * Resolution rules mirror the spec:
 *   - `pattern`: the user's full preferred pattern (`patternForKey(dateFormat.value)`) UNLESS
 *     `dateFormat.source === "DEFAULT"` (nothing set anywhere), in which case `pattern` is null so
 *     consumers fall back to the browser locale rather than a hardcoded pattern.
 *   - `timezone`: the resolved IANA name UNLESS `timezone.source === "DEFAULT"`, in which case it
 *     is null so consumers use the browser's local zone.
 *
 * Non-blocking: while the query is pending / errored, `pattern` and `timezone` stay null, so
 * children render with the browser-locale fallback instead of suspending or crashing.
 */
export function DatePreferencesProvider({ children }: { children: React.ReactNode }) {
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

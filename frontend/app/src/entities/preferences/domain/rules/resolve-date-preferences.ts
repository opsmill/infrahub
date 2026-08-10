import type { ResolvedDatePreferences } from "@/shared/context/date-preferences-context";

import type {
  EffectivePreferences,
  Preference,
} from "@/entities/preferences/domain/model/preference";
import { dateFormatPattern } from "@/entities/preferences/domain/rules/date-format";

/**
 * The timezone a caller inherits when they set none of their own — the global layer, or null for the
 * browser zone. A `USER` source yields null: that value is exactly what clearing the field discards,
 * and the API resolves the inherited one away once an override wins.
 */
export function inheritedTimezone(timezone: Preference): string | null {
  return timezone.source === "GLOBAL" ? (timezone.value ?? null) : null;
}

// A `DEFAULT` source (or missing value/data) resolves to null so consumers fall back to the browser locale/zone.
export function resolveDatePreferences(
  preferences: EffectivePreferences | undefined
): ResolvedDatePreferences {
  const dateFormat = preferences?.dateFormat;
  const timezone = preferences?.timezone;

  return {
    pattern:
      dateFormat && dateFormat.source !== "DEFAULT" && dateFormat.value
        ? dateFormatPattern(dateFormat.value)
        : null,
    timezone: timezone && timezone.source !== "DEFAULT" ? (timezone.value ?? null) : null,
  };
}

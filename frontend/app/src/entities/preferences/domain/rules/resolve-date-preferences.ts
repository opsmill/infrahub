import type { ResolvedDatePreferences } from "@/shared/context/date-preferences-context";

import type {
  EffectivePreference,
  EffectivePreferences,
} from "@/entities/preferences/domain/model/preference";
import { dateFormatPattern } from "@/entities/preferences/domain/rules/date-format";

/**
 * The value a caller inherits when they set none of their own: the global layer, or null for the
 * client default. Read from the `inherited` layer, so a caller's own override does not hide it.
 */
export function inheritedValue<T>(preference: EffectivePreference<T>): T | null {
  return preference.inherited.source === "GLOBAL" ? (preference.inherited.value ?? null) : null;
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

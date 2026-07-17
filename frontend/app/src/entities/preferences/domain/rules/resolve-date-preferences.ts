import type { ResolvedDatePreferences } from "@/shared/context/date-preferences-context";

import type { EffectivePreferences } from "@/entities/preferences/domain/model/preference";
import { patternForKey } from "@/entities/preferences/domain/rules/date-format";

// A `DEFAULT` source (or missing value/data) resolves to null so consumers fall back to the browser locale/zone.
export function resolveDatePreferences(
  preferences: EffectivePreferences | undefined
): ResolvedDatePreferences {
  const dateFormat = preferences?.dateFormat;
  const timezone = preferences?.timezone;

  return {
    pattern:
      dateFormat && dateFormat.source !== "DEFAULT" && dateFormat.value
        ? patternForKey(dateFormat.value)
        : null,
    timezone: timezone && timezone.source !== "DEFAULT" ? (timezone.value ?? null) : null,
  };
}

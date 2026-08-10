import type { ResolvedDatePreferences } from "@/shared/context/date-preferences-context";

import type {
  EffectivePreferences,
  Preference,
} from "@/entities/preferences/domain/model/preference";
import { dateFormatPattern } from "@/entities/preferences/domain/rules/date-format";

/**
 * The timezone that would apply if the caller held no override of their own.
 * A `USER` source yields null: the caller's own value is precisely what an unset field discards, and
 * the API resolves the inherited one away once an override wins, so null (browser zone) is the only
 * honest answer.
 */
export function inheritedTimezone(timezone: Preference): string | null {
  return timezone.source === "USER" ? null : (timezone.value ?? null);
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

import React from "react";

import {
  DatePreferencesContext,
  formatWithPreferences,
} from "@/shared/context/date-preferences-context";
import type { DateInput } from "@/shared/utils/date";

/** Formats a license date as a day in the preferred date format but in UTC, since license days are counted in UTC. */
export function useFormatLicenseDay() {
  const preferences = React.use(DatePreferencesContext);

  return (date: DateInput) =>
    formatWithPreferences(date, { pattern: preferences?.pattern ?? null, timezone: "UTC" }, "date");
}

import { Card, CardHeader } from "@infrahub/ui";

import { PreferencesForm } from "@/entities/preferences/ui/preferences-form";

export function UserPreferencesCard() {
  return (
    <Card>
      <CardHeader>Preferences</CardHeader>
      <p className="px-3 py-2 text-gray-600 text-sm">
        Personal overrides of the organisation defaults. A field with no personal override inherits
        the organisation-wide value, or the browser default when none is set. Selecting a value
        overrides it; re-selecting the currently-selected value clears the override.
      </p>

      <PreferencesForm />
    </Card>
  );
}

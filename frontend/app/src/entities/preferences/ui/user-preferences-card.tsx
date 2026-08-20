import { Card, CardHeader } from "@infrahub/ui";

import { PreferencesForm } from "@/entities/preferences/ui/preferences-form";

export function UserPreferencesCard() {
  return (
    <Card>
      <CardHeader>Preferences</CardHeader>

      <PreferencesForm />
    </Card>
  );
}

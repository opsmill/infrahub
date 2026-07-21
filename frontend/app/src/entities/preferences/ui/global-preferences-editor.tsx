import { Card, CardHeader } from "@infrahub/ui";

import { GlobalPreferencesForm } from "@/entities/preferences/ui/global-preferences-form";

export function GlobalPreferencesEditor() {
  return (
    <main className="p-2">
      <Card className="w-full max-w-3xl">
        <CardHeader>Global date and time</CardHeader>

        <GlobalPreferencesForm />
      </Card>
    </main>
  );
}

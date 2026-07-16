import { Card, CardHeader } from "@infrahub/ui";

import { GlobalPreferencesForm } from "@/entities/preferences/ui/global-preferences-form";

export function GlobalPreferencesEditor() {
  return (
    <main className="p-2">
      <Card className="w-full max-w-3xl">
        <CardHeader>Global date and time</CardHeader>
        <p className="px-3 py-2 text-gray-600 text-sm">
          Defaults applied to every user unless they set a personal override.
        </p>

        <GlobalPreferencesForm />
      </Card>
    </main>
  );
}

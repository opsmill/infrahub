import { Card, CardHeader } from "@infrahub/ui";

import { GlobalPreferencesForm } from "@/entities/preferences/ui/global-preferences-form";
import { InstanceIdentityForm } from "@/entities/preferences/ui/instance-identity-form";

export function GlobalPreferencesEditor() {
  return (
    <main className="space-y-2 p-2">
      <Card className="w-full max-w-3xl">
        <CardHeader>Global date and time</CardHeader>

        <GlobalPreferencesForm />
      </Card>

      <Card className="w-full max-w-3xl">
        <CardHeader>Instance identity</CardHeader>

        <InstanceIdentityForm />
      </Card>
    </main>
  );
}

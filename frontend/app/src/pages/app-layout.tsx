import { useState } from "react";
import { Outlet } from "react-router";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { ConfigWizard } from "@/entities/config-wizard/ui/config-wizard";
import { useHasUserSchemas } from "@/entities/config-wizard/hooks/use-has-user-schemas";
import { AppHeader } from "@/entities/navigation/ui/app-header";
import { AppSidebar } from "@/entities/navigation/ui/sidebar/app-sidebar";

function AppLayout() {
  const { isAuthenticated } = useAuth();
  const hasUserSchemas = useHasUserSchemas();
  const [wizardDismissed, setWizardDismissed] = useState(false);

  const showWizard = isAuthenticated && !hasUserSchemas && !wizardDismissed;

  return (
    <div className="h-screen w-screen bg-stone-100 p-0.5 text-stone-800">
      <div className="flex h-full w-full gap-0.5">
        <AppSidebar />

        <div className="flex h-full grow flex-col gap-0.5 overflow-hidden">
          <AppHeader />

          <Outlet />
        </div>
      </div>

      <ConfigWizard isOpen={showWizard} onDismiss={() => setWizardDismissed(true)} />
    </div>
  );
}

export const Component = AppLayout;

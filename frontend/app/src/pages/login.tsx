import { Navigate, useLocation, useSearchParams } from "react-router";

import type { RestErrorItem } from "@/shared/api/rest/fetch";
import { InfrahubLogo } from "@/shared/components/ui/infrahub-logo";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { LoginMethodPicker } from "@/entities/authentication/ui/login-method-picker";
import { resolveLoginRedirect } from "@/entities/authentication/ui/routing/login-redirect";
import { InstanceBadge } from "@/entities/preferences/ui/instance-badge";
import { InstanceColorBar } from "@/entities/preferences/ui/instance-color-bar";

function LoginPage() {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return <Navigate to={resolveLoginRedirect(location, searchParams)} replace />;
  }

  const errors = location?.state?.errors as RestErrorItem[] | undefined;

  return (
    <div className="flex h-screen w-screen flex-col bg-background">
      <InstanceColorBar />

      {/* biome-ignore lint/nursery/noTailwindArbitraryValue: no-utility: viewport-relative padding (25vh) has no spacing token */}
      <div className="min-h-0 flex-1 overflow-auto py-[25vh]">
        <div className="m-auto flex w-full max-w-sm flex-col items-center gap-6">
          <InstanceBadge />

          <InfrahubLogo className="h-12" />

          <h1 className="font-semibold text-foreground text-xl">Log in to your account</h1>

          <LoginMethodPicker />

          {errors?.map((error, index) => (
            <p
              key={`${index}-${error.extensions.code}-${error.message}`}
              className="mt-2 text-danger text-sm"
            >
              ({error.extensions.code}) {error.message}
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}

export const Component = LoginPage;

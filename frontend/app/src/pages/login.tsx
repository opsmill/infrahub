import { Navigate, useLocation, useSearchParams } from "react-router";

import InfrahubLogo from "@/assets/Infrahub-SVG-hori.svg?react";

import type { RestErrorItem } from "@/shared/api/rest/fetch";

import { LoginMethodPicker } from "@/entities/authentication/ui/login-method-picker";
import { useAuth } from "@/entities/authentication/ui/useAuth";
import { resolveLoginRedirect } from "@/entities/authentication/utils";

function LoginPage() {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return <Navigate to={resolveLoginRedirect(location, searchParams)} replace />;
  }

  const errors = location?.state?.errors as RestErrorItem[] | undefined;

  return (
    <div className="h-screen w-screen overflow-auto bg-stone-100 py-[25vh]">
      <div className="m-auto flex w-full max-w-sm flex-col items-center gap-6">
        <InfrahubLogo className="h-12" />

        <h1 className="font-semibold text-neutral-900 text-xl">Log in to your account</h1>

        <LoginMethodPicker />

        {errors?.map((error, index) => (
          <p
            key={`${index}-${error.extensions.code}-${error.message}`}
            className="mt-2 text-red-500 text-sm"
          >
            ({error.extensions.code}) {error.message}
          </p>
        ))}
      </div>
    </div>
  );
}

export const Component = LoginPage;

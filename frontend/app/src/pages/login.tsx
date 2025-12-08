import { Navigate, useLocation } from "react-router";

import InfrahubLogo from "@/assets/Infrahub-SVG-hori.svg?react";

import { Login } from "@/entities/authentication/ui/login";
import { useAuth } from "@/entities/authentication/ui/useAuth";

function LoginPage() {
  const location = useLocation();
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    const from = (location.state?.from?.pathname || "/") + (location.state?.from?.search ?? "");
    return <Navigate to={from} replace />;
  }

  return (
    <div className="h-screen w-screen overflow-auto bg-stone-100 py-[25vh] dark:bg-slate-800">
      <div className="m-auto flex w-full max-w-sm flex-col items-center gap-6">
        <InfrahubLogo className="h-12" />

        <h1 className="font-semibold text-neutral-900 text-xl dark:text-neutral-100">
          Log in to your account
        </h1>

        <Login />

        {location?.state?.errors?.map(
          (error: { extensions: { code: number }; message: string }, index: number) => (
            <p key={index} className="mt-2 text-red-500 text-sm">
              ({error.extensions.code}) {error.message}
            </p>
          )
        )}
      </div>
    </div>
  );
}

export const Component = LoginPage;

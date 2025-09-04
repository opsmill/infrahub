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
    <div className="bg-stone-100 h-screen w-screen py-[25vh] overflow-auto">
      <div className="flex flex-col items-center gap-6 w-full max-w-sm m-auto">
        <InfrahubLogo className="h-12" />

        <h1 className="text-xl font-semibold text-neutral-900">Log in to your account</h1>

        <Login />

        {location?.state?.errors?.map(
          (error: { extensions: { code: number }; message: string }, index: number) => (
            <p key={index} className="text-red-500 text-sm mt-2">
              ({error.extensions.code}) {error.message}
            </p>
          )
        )}
      </div>
    </div>
  );
}

export const Component = LoginPage;

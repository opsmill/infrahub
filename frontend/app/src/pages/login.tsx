import { useAuth } from "@/hooks/useAuth";
import { ReactComponent as InfrahubLogo } from "@/images/Infrahub-SVG-hori.svg";
import { Login } from "@/screens/authentification/login";
import { Navigate, useLocation } from "react-router-dom";

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
        <InfrahubLogo className="h-12" alt="Intrahub logo" />

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

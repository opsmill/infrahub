import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/useAuth";
import { ReactComponent as InfrahubLogo } from "@/images/Infrahub-SVG-verti.svg";
import { SignIn } from "@/screens/authentification/sign-in";
import Content from "@/screens/layout/content";
import { Navigate, useLocation } from "react-router-dom";

function SignInPage() {
  let location = useLocation();
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    const from = (location.state?.from?.pathname || "/") + (location.state?.from?.search ?? "");
    return <Navigate to={from} replace />;
  }

  return (
    <Content className="flex justify-center items-center bg-gray-200 p-2 h-screen">
      <Card className="w-full max-w-lg shadow">
        <div className="flex flex-col items-center p-8">
          <InfrahubLogo className="h-28 w-28" alt="Intrahub logo" />

          <h2 className="my-8 text-2xl font-semibold text-gray-900">Sign in to your account</h2>

          <SignIn />

          {location?.state?.errors?.map(
            (error: { extensions: { code: number }; message: string }, index: number) => (
              <p key={index} className="text-red-500 text-sm mt-2">
                ({error.extensions.code}) {error.message}
              </p>
            )
          )}
        </div>
      </Card>
    </Content>
  );
}

export const Component = SignInPage;

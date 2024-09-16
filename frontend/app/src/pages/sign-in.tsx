import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/useAuth";
import { ReactComponent as InfrahubLogo } from "@/images/Infrahub-SVG-verti.svg";
import Content from "@/screens/layout/content";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import InputField from "@/components/form/fields/input.field";
import { isRequired } from "@/components/form/utils/validation";
import PasswordInputField from "@/components/form/fields/password-input.field";
import { Form, FormSubmit } from "@/components/ui/form";
import { GoogleLoginButton } from "@/screens/authentification/components/google-login-button";

function SignInPage() {
  return (
    <Content className="flex justify-center items-center bg-gray-200 p-2 h-screen">
      <Card className="w-full max-w-lg shadow">
        <div className="flex flex-col items-center p-8">
          <InfrahubLogo className="h-28 w-28" alt="Intrahub logo" />

          <h2 className="my-8 text-2xl font-semibold text-gray-900">Sign in to your account</h2>

          <SignInForm />

          <div className="h-px w-full bg-custom-blue-700 my-4" />

          <GoogleLoginButton />
        </div>
      </Card>
    </Content>
  );
}

const SignInForm = () => {
  let navigate = useNavigate();
  let location = useLocation();
  const { signIn } = useAuth();

  const from = (location.state?.from?.pathname || "/") + (location.state?.from?.search ?? "");

  return (
    <Form
      className="w-full"
      onSubmit={async (formData) => {
        const data = {
          username: formData.username.value as string,
          password: formData.password.value as string,
        };
        await signIn(data, () => navigate(from));
      }}>
      <InputField name="username" label="Username" rules={{ validate: { required: isRequired } }} />

      <PasswordInputField
        name="password"
        label="Password"
        rules={{ validate: { required: isRequired } }}
      />

      <FormSubmit className="w-full h-10">Sign in</FormSubmit>
    </Form>
  );
};

export function Component() {
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <SignInPage />;
}

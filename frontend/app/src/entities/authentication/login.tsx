import { configState } from "@/config/config.atom";
import { LoginWithSSOButtons } from "@/entities/authentication/login-sso-buttons";
import { Button } from "@/shared/components/buttons/button-primitive";
import InputField from "@/shared/components/form/fields/input.field";
import PasswordInputField from "@/shared/components/form/fields/password-input.field";
import { isRequired } from "@/shared/components/form/utils/validation";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { useAuth } from "@/shared/hooks/useAuth";
import { classNames } from "@/shared/utils/common";
import { useAtomValue } from "jotai";
import { useState } from "react";

export const Login = () => {
  const config = useAtomValue(configState);
  const [displaySSO, setDisplaySSO] = useState(true);

  if (config && config.sso.enabled && config.sso.providers.length > 0) {
    return displaySSO ? (
      <>
        <LoginWithSSOButtons providers={config.sso.providers} className="animate-in fade-in" />
        <Button
          variant="ghost"
          onClick={() => setDisplaySSO(!displaySSO)}
          className="text-sm text-cyan-900 hover:underline hover:bg-transparent"
        >
          Log in with your credentials
        </Button>
      </>
    ) : (
      <>
        <LoginForm className="animate-in fade-in" />
        <Button
          variant="ghost"
          onClick={() => setDisplaySSO(!displaySSO)}
          className="text-sm text-cyan-900 hover:underline hover:bg-transparent"
        >
          Log in with SSO
        </Button>
      </>
    );
  }

  return <LoginForm />;
};

export const LoginForm = ({ className }: { className?: string }) => {
  const { login } = useAuth();

  return (
    <Form
      className={classNames("w-full", className)}
      onSubmit={async (formData) => {
        const data = {
          username: formData.username.value as string,
          password: formData.password.value as string,
        };
        await login(data);
      }}
    >
      <InputField name="username" label="Username" rules={{ validate: { required: isRequired } }} />

      <PasswordInputField
        name="password"
        label="Password"
        rules={{ validate: { required: isRequired } }}
      />

      <FormSubmit className="w-full h-10">Log in</FormSubmit>
    </Form>
  );
};

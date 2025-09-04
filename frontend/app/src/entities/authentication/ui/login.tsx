import { useState } from "react";

import { Button } from "@/shared/components/buttons/button-primitive";
import InputField from "@/shared/components/form/fields/input.field";
import PasswordInputField from "@/shared/components/form/fields/password-input.field";
import { isRequired } from "@/shared/components/form/utils/validation";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { classNames } from "@/shared/utils/common";

import { LoginWithSSOButtons } from "@/entities/authentication/ui/login-sso-buttons";
import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useConfig } from "@/entities/config/ui/config-provider";

export const Login = () => {
  const config = useConfig();
  const [displaySSO, setDisplaySSO] = useState(true);

  if (config && config.sso.enabled && config.sso.providers && config.sso.providers.length > 0) {
    return displaySSO ? (
      <>
        <LoginWithSSOButtons providers={config.sso.providers} className="fade-in animate-in" />
        <Button
          variant="ghost"
          onClick={() => setDisplaySSO(!displaySSO)}
          className="text-cyan-900 text-sm hover:bg-transparent hover:underline"
        >
          Log in with your credentials
        </Button>
      </>
    ) : (
      <>
        <LoginForm className="fade-in animate-in" />
        <Button
          variant="ghost"
          onClick={() => setDisplaySSO(!displaySSO)}
          className="text-cyan-900 text-sm hover:bg-transparent hover:underline"
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

      <FormSubmit className="h-10 w-full">Log in</FormSubmit>
    </Form>
  );
};

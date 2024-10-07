import InputField from "@/components/form/fields/input.field";
import PasswordInputField from "@/components/form/fields/password-input.field";
import { isRequired } from "@/components/form/utils/validation";
import { Divider } from "@/components/ui/divider";
import { Form, FormSubmit } from "@/components/ui/form";
import { useAuth } from "@/hooks/useAuth";
import { SignInWithSSOButtons } from "@/screens/authentification/sign-in-sso-buttons";
import { configState } from "@/state/atoms/config.atom";
import { useAtomValue } from "jotai/index";

export const SignIn = () => {
  const config = useAtomValue(configState);

  if (config && config.sso.enabled && config.sso.providers.length > 0) {
    return (
      <>
        <SignInWithSSOButtons providers={config.sso.providers} />
        <Divider>Or</Divider>
        <SignInForm />
      </>
    );
  }

  return <SignInForm />;
};

export const SignInForm = () => {
  const { signIn } = useAuth();

  return (
    <Form
      className="w-full"
      onSubmit={async (formData) => {
        const data = {
          username: formData.username.value as string,
          password: formData.password.value as string,
        };
        await signIn(data);
      }}
    >
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

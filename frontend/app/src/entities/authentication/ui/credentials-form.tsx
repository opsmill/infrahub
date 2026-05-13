import { toast } from "react-toastify";

import InputField from "@/shared/components/form/fields/input.field";
import PasswordInputField from "@/shared/components/form/fields/password-input.field";
import { isRequired } from "@/shared/components/form/utils/validation";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { classNames } from "@/shared/utils/common";

import type { LoginError, UserToken } from "@/entities/authentication/types";
import { useAuth } from "@/entities/authentication/ui/useAuth";

export interface CredentialsFormProps {
  onSubmit: (values: { username: string; password: string }) => Promise<UserToken>;
  className?: string;
  submitLabel?: string;
}

function toLoginError(error: unknown): LoginError {
  const status = (error as { status?: number } | null)?.status;

  if (status === 401) {
    return { code: "invalid_credentials", message: "Invalid username or password" };
  }
  if (typeof status === "number" && status >= 500) {
    return { code: "server", message: "Authentication service unavailable" };
  }

  const isOffline = typeof navigator !== "undefined" && navigator.onLine === false;
  const isFetchFailure = error instanceof TypeError;
  if (status === undefined && (isOffline || isFetchFailure)) {
    return { code: "network", message: "Network error — check your connection" };
  }

  return { code: "unknown", message: "Could not log in" };
}

export const CredentialsForm = ({
  onSubmit,
  className,
  submitLabel = "Log in",
}: CredentialsFormProps) => {
  const { setToken } = useAuth();

  return (
    <Form
      className={classNames("w-full", className)}
      onSubmit={async (formData) => {
        const values = {
          username: formData.username.value as string,
          password: formData.password.value as string,
        };
        try {
          const result = await onSubmit(values);
          setToken(result);
        } catch (error) {
          const loginError = toLoginError(error);
          console.error("Error when logging in: ", error);
          toast(<Alert type={ALERT_TYPES.ERROR} message={loginError.message} />, {
            toastId: `alert-error-sign-in-${loginError.code}`,
          });
        }
      }}
    >
      <InputField
        name="username"
        label="Username"
        rules={{ validate: { required: isRequired } }}
        autoFocus
      />

      <PasswordInputField
        name="password"
        label="Password"
        rules={{ validate: { required: isRequired } }}
      />

      <FormSubmit className="h-10 w-full">{submitLabel}</FormSubmit>
    </Form>
  );
};

import { toast } from "react-toastify";

import InputField from "@/shared/components/form/fields/input.field";
import PasswordInputField from "@/shared/components/form/fields/password-input.field";
import { isRequired } from "@/shared/components/form/utils/validation";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { classNames } from "@/shared/utils/common";

import { LOGIN_ERRORS } from "@/entities/authentication/constants";
import type { LoginError, UserToken } from "@/entities/authentication/types";
import { useAuth } from "@/entities/authentication/ui/useAuth";

export interface CredentialsFormProps {
  onSubmit: (values: { username: string; password: string }) => Promise<UserToken>;
  className?: string;
  submitLabel?: string;
}

function getErrorStatus(error: unknown): number | undefined {
  if (error && typeof error === "object" && "status" in error) {
    const { status } = error;
    return typeof status === "number" ? status : undefined;
  }
  return;
}

function toLoginError(error: unknown): LoginError {
  const status = getErrorStatus(error);

  if (status === 401) {
    return LOGIN_ERRORS.invalid_credentials;
  }
  if (status !== undefined && status >= 500) {
    return LOGIN_ERRORS.server;
  }

  const isOffline = typeof navigator !== "undefined" && navigator.onLine === false;
  const isFetchFailure = error instanceof TypeError;
  if (status === undefined && (isOffline || isFetchFailure)) {
    return LOGIN_ERRORS.network;
  }

  return LOGIN_ERRORS.unknown;
}

function readStringField(field: unknown): string {
  if (field && typeof field === "object" && "value" in field) {
    const { value } = field;
    return typeof value === "string" ? value : "";
  }
  return "";
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
          username: readStringField(formData.username),
          password: readStringField(formData.password),
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

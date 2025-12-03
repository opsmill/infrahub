import { toast } from "react-toastify";

import DynamicForm from "@/shared/components/form/dynamic-form";
import type { FormFieldValue } from "@/shared/components/form/type";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { classNames } from "@/shared/utils/common";

import { validateTextAttribute } from "@/entities/schema/utils/validation/validate-text-attribute";
import { useCreateAccountTokenMutation } from "@/entities/user-profile/domain/create-account-token.mutation";

export interface AccountTokenCreateFormProps {
  onSuccess: (data: { token: string }) => Promise<void>;
  className?: string;
}

export function AccountTokenCreateForm({ onSuccess, className }: AccountTokenCreateFormProps) {
  const createAccountToken = useCreateAccountTokenMutation();

  return (
    <DynamicForm
      className={classNames("flex flex-1 flex-col overflow-auto p-4", className)}
      fields={[
        {
          name: "name",
          label: "Name",
          type: "Text",
          rules: {
            required: true,
            validate: (formFieldValue: FormFieldValue) => {
              const value = formFieldValue.value as string | null;
              const validation = validateTextAttribute({ isRequired: true }, value);
              return validation.success || validation.error;
            },
          },
        },
        {
          name: "expiration",
          label: "Expiration",
          disabled: false,
          type: "DateTime",
        },
      ]}
      onSubmit={async (formData) => {
        const tokenName = formData.name?.value?.toString();
        const tokenExpirationDate = formData.expiration?.value?.toString();

        if (!tokenName) return;

        await createAccountToken.mutateAsync(
          {
            tokenName,
            tokenExpirationDate,
          },
          {
            onSuccess: async (newToken) => {
              toast(() => <Alert type={ALERT_TYPES.SUCCESS} message="Account token created" />, {
                toastId: "alert-success-account-token-created",
              });

              if (onSuccess) await onSuccess(newToken);
            },
            onError: (error) => {
              console.error("An error occurred while creating the object: ", error);
            },
          }
        );
      }}
    />
  );
}

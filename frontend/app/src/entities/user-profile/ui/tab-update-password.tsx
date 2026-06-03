import { gql, useQuery } from "@apollo/client";
import { toast } from "react-toastify";

import { useMutation } from "@/shared/api/graphql/useQuery";
import PasswordInputField from "@/shared/components/form/fields/password-input.field";
import { isRequired } from "@/shared/components/form/utils/validation";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Card } from "@/shared/components/ui/card";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import { UPDATE_ACCOUNT_PASSWORD } from "@/entities/user-profile/api/updateAccountPassword";

const GET_ACCOUNT_PROFILE_PASSWORD_MANAGEMENT = gql`
  query GET_ACCOUNT_PROFILE_PASSWORD_MANAGEMENT {
    AccountProfile {
      id
      is_externally_managed
    }
  }
`;

type UpdatePasswordFormData = {
  newPassword: string;
  confirmPassword: string;
};

export default function TabUpdatePassword() {
  const { data, loading } = useQuery(GET_ACCOUNT_PROFILE_PASSWORD_MANAGEMENT);
  const account = data?.AccountProfile;
  const [updateAccountPassword] = useMutation(UPDATE_ACCOUNT_PASSWORD);

  const onSubmit = async ({ newPassword }: UpdatePasswordFormData) => {
    try {
      await updateAccountPassword({ variables: { password: newPassword } });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Password updated" />);
    } catch (error) {
      console.error("Error while updating the password: ", error);
    }
  };

  if (loading) {
    return <LoadingIndicator className="h-full" />;
  }

  if (account?.is_externally_managed !== false) {
    return (
      <main className="p-2">
        <Card className="m-auto w-full max-w-md">
          <h3 className="mb-2 font-semibold leading-6">Password managed externally</h3>
          <p className="text-gray-600 text-sm">
            This account authenticates through an external directory. Change your password in the
            directory provider; local password updates are not accepted.
          </p>
        </Card>
      </main>
    );
  }

  return (
    <main className="p-2">
      <Card className="m-auto w-full max-w-md">
        <h3 className="mb-4 font-semibold leading-6">Update your password</h3>

        <Form
          onSubmit={async (formData) => {
            const data: UpdatePasswordFormData = {
              newPassword: formData.newPassword.value as string,
              confirmPassword: formData.confirmPassword.value as string,
            };
            await onSubmit(data);
          }}
        >
          <PasswordInputField
            name="newPassword"
            label="New password"
            rules={{
              required: true,
              validate: {
                required: isRequired,
              },
            }}
          />

          <PasswordInputField
            name="confirmPassword"
            label="Confirm password"
            rules={{
              required: true,
              validate: {
                required: isRequired,
                isSamePassword: ({ value }, fieldValues) => {
                  return value === fieldValues.newPassword.value || "Passwords don't match";
                },
              },
            }}
          />

          <FormSubmit>Update password</FormSubmit>
        </Form>
      </Card>
    </main>
  );
}

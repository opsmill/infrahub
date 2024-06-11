import DynamicForm from "@/components/form/dynamic-form";
import { DynamicFieldProps } from "@/components/form/fields/common";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { UPDATE_ACCOUNT_PASSWORD } from "@/graphql/mutations/accounts/updateAccountPassword";
import Content from "@/screens/layout/content";
import { useMutation } from "@apollo/client";
import { toast } from "react-toastify";

type UpdatePasswordFormData = {
  newPassword: string;
  confirmPassword: string;
};

const fields: Array<DynamicFieldProps> = [
  {
    name: "newPassword",
    label: "New password",
    type: "Password",
    rules: {
      required: true,
    },
  },
  {
    name: "confirmPassword",
    label: "Confirm password",
    type: "Password",
    rules: {
      required: true,
      validate: (value, fieldValues) => {
        return value === fieldValues.newPassword || "Passwords don't match.";
      },
    },
  },
];

export default function TabPreferences() {
  const [updateAccountPassword] = useMutation(UPDATE_ACCOUNT_PASSWORD);

  const onSubmit = async ({ newPassword }: UpdatePasswordFormData) => {
    try {
      await updateAccountPassword({ variables: { password: newPassword } });

      toast(() => <Alert type={ALERT_TYPES.SUCCESS} message="Password updated" />);
    } catch (error) {
      console.error("Error while updating the password: ", error);
    }
  };

  return (
    <Content className="p-2">
      <Card className="m-auto w-full max-w-md">
        <h3 className="leading-6 font-semibold mb-4">Update your password</h3>

        <DynamicForm
          fields={fields}
          onSubmit={async (data) => await onSubmit(data as UpdatePasswordFormData)}
          submitLabel="Update password"
        />
      </Card>
    </Content>
  );
}

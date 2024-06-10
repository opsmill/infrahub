import { gql } from "@apollo/client";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { ACCOUNT_SELF_UPDATE_OBJECT } from "../../config/constants";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { updateObjectWithId } from "../../graphql/mutations/objects/updateObjectWithId";
import { stringifyWithoutQuotes } from "../../utils/string";
import Content from "../layout/content";
import { Card } from "../../components/ui/card";
import DynamicForm from "../../components/form/dynamic-form";
import { DynamicFieldProps } from "../../components/form/fields/common";

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
  const onSubmit = async ({ newPassword, confirmPassword }: any) => {
    if (newPassword !== confirmPassword) {
      toast(() => <Alert type={ALERT_TYPES.WARNING} message="Passwords must be the same" />);
      return;
    }

    try {
      const mutationString = updateObjectWithId({
        kind: ACCOUNT_SELF_UPDATE_OBJECT,
        data: stringifyWithoutQuotes({
          password: newPassword,
        }),
      });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({ mutation });

      toast(() => <Alert type={ALERT_TYPES.SUCCESS} message="Password updated" />);
    } catch (error) {
      console.log("Error while updating the password: ", error);
    }
  };

  return (
    <Content className="p-2">
      <Card className="m-auto w-full max-w-md">
        <h3 className="leading-6 font-semibold mb-4">Update your password</h3>

        <DynamicForm fields={fields} onSubmit={onSubmit} submitLabel="Update password" />
      </Card>
    </Content>
  );
}

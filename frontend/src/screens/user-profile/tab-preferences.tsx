import { gql } from "@apollo/client";
import { useState } from "react";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { ACCOUNT_SELF_UPDATE_OBJECT } from "../../config/constants";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { updateObjectWithId } from "../../graphql/mutations/objects/updateObjectWithId";
import { stringifyWithoutQuotes } from "../../utils/string";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import { Form } from "../edit-form-hook/form";
import Content from "../layout/content";
import { Card } from "../../components/ui/card";

const fields: DynamicFieldData[] = [
  {
    name: "newPassword",
    label: "New password",
    type: "password",
    value: "",
    config: {
      required: "Required",
    },
  },
  {
    name: "confirmPassword",
    label: "Confirm password",
    type: "password",
    value: "",
    config: {
      required: "Required",
    },
  },
];

export default function TabPreferences() {
  const [isLoading, setIsLoading] = useState(false);

  const onSubmit = async ({ newPassword, confirmPassword }: any) => {
    if (newPassword !== confirmPassword) {
      toast(() => <Alert type={ALERT_TYPES.WARNING} message="Passwords must be the same" />);
      return;
    }

    setIsLoading(true);

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

    setIsLoading(false);
  };

  return (
    <Content className="p-2">
      <Card className="m-auto w-full max-w-md">
        <h3 className="leading-6 font-semibold">Update your password</h3>

        <Form
          onSubmit={onSubmit}
          fields={fields}
          submitLabel={"Update password"}
          isLoading={isLoading}
        />
      </Card>
    </Content>
  );
}

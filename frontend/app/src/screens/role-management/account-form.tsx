import { Button } from "@/components/buttons/button-primitive";
import { NodeFormProps } from "@/components/form/node-form";
import { FormFieldValue } from "@/components/form/type";
import { getCurrentFieldValue } from "@/components/form/utils/getFieldDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/components/form/utils/mutations/getCreateMutationFromFormData";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { Form, FormSubmit } from "@/components/ui/form";
import { ACCOUNT_GROUP_OBJECT, ACCOUNT_OBJECT, OBJECT_PERMISSION_OBJECT } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { createObject } from "@/graphql/mutations/objects/createObject";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { AttributeType, RelationshipType } from "@/utils/getObjectItemDisplayValue";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { FieldValues, useForm } from "react-hook-form";
import { toast } from "react-toastify";

import RelationshipField from "@/components/form/fields/relationship.field";
import InputField from "@/components/form/fields/input.field";
import { DropdownOption } from "@/components/inputs/dropdown";
import { useSchema } from "@/hooks/useSchema";
import DropdownField from "@/components/form/fields/dropdown.field";

interface NumberPoolFormProps extends Pick<NodeFormProps, "onSuccess"> {
  currentObject?: Record<string, AttributeType | RelationshipType>;
  onCancel?: () => void;
  onUpdateComplete?: () => void;
}

export const AccountForm = ({
  currentObject,
  onSuccess,
  onCancel,
  onUpdateComplete,
}: NumberPoolFormProps) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const { schema } = useSchema(ACCOUNT_GROUP_OBJECT);

  const defaultValues = {
    name: getCurrentFieldValue("name", currentObject),
    password: getCurrentFieldValue("password", currentObject),
    description: getCurrentFieldValue("description", currentObject),
    label: getCurrentFieldValue("label", currentObject),
    account_type: getCurrentFieldValue("account_type", currentObject),
    groups: getCurrentFieldValue("groups", currentObject),
  };

  const form = useForm<FieldValues>({
    defaultValues,
  });

  async function handleSubmit(data: Record<string, FormFieldValue>) {
    try {
      const newObject = getCreateMutationFromFormDataOnly(data, currentObject);

      if (!Object.keys(newObject).length) {
        return;
      }

      const mutationString = currentObject
        ? updateObjectWithId({
            kind: ACCOUNT_OBJECT,
            data: stringifyWithoutQuotes({
              id: currentObject.id,
              ...newObject,
            }),
          })
        : createObject({
            kind: ACCOUNT_OBJECT,
            data: stringifyWithoutQuotes({
              ...newObject,
            }),
          });

      const mutation = gql`
        ${mutationString}
      `;

      const result = await graphqlClient.mutate({
        mutation,
        context: {
          branch: branch?.name,
          date,
        },
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Object permission created"} />, {
        toastId: "alert-success-object-permission-created",
      });

      if (onSuccess) await onSuccess(result?.data?.[`${OBJECT_PERMISSION_OBJECT}Create`]);
      if (onUpdateComplete) await onUpdateComplete();
    } catch (error: unknown) {
      console.error("An error occurred while creating the object: ", error);
    }
  }

  const typeOptions: DropdownOption[] =
    schema?.attributes
      ?.find((attribute) => attribute.name === "account_type")
      ?.enum?.map((data) => ({ value: data as string, label: data as string })) ?? [];

  return (
    <div className={"bg-custom-white flex flex-col flex-1 overflow-auto p-4"}>
      <Form form={form} onSubmit={handleSubmit}>
        <InputField name="name" label="Name" />
        <InputField name="password" label="Password" type="password" />
        <InputField name="description" label="Description" />

        <DropdownField name="account_type" label="Type" items={typeOptions} />

        <RelationshipField
          name="groups"
          label="Groups"
          relationship={{
            name: "groups",
            peer: ACCOUNT_GROUP_OBJECT,
            cardinality: "many",
          }}
          schema={schema}
        />

        <div className="text-right">
          {onCancel && (
            <Button variant="outline" className="mr-2" onClick={onCancel}>
              Cancel
            </Button>
          )}

          <FormSubmit>{currentObject ? "Update" : "Create"}</FormSubmit>
        </div>
      </Form>
    </div>
  );
};
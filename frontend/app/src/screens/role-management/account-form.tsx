import { Button } from "@/components/buttons/button-primitive";
import InputField from "@/components/form/fields/input.field";
import RelationshipField from "@/components/form/fields/relationship.field";
import { NodeFormProps } from "@/components/form/node-form";
import { FormFieldValue } from "@/components/form/type";
import { getCurrentFieldValue } from "@/components/form/utils/getFieldDefaultValue";
import { getRelationshipDefaultValue } from "@/components/form/utils/getRelationshipDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/components/form/utils/mutations/getCreateMutationFromFormData";
import { isRequired } from "@/components/form/utils/validation";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Form, FormSubmit } from "@/components/ui/form";
import { ACCOUNT_GROUP_OBJECT, ACCOUNT_OBJECT, OBJECT_PERMISSION_OBJECT } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { createObject } from "@/graphql/mutations/objects/createObject";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { useSchema } from "@/hooks/useSchema";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { AttributeType, RelationshipType } from "@/utils/getObjectItemDisplayValue";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { FieldValues, useForm } from "react-hook-form";
import { toast } from "react-toastify";

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
  const { schema } = useSchema(ACCOUNT_OBJECT);

  const groups = getRelationshipDefaultValue({
    relationshipData: currentObject?.member_of_groups?.value,
  });

  const defaultValues = {
    name: getCurrentFieldValue("name", currentObject),
    password: getCurrentFieldValue("password", currentObject),
    description: getCurrentFieldValue("description", currentObject),
    label: getCurrentFieldValue("label", currentObject),
    member_of_groups: groups,
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

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Account created"} />, {
        toastId: "alert-success-account-created",
      });

      if (onSuccess) await onSuccess(result?.data?.[`${OBJECT_PERMISSION_OBJECT}Create`]);
      if (onUpdateComplete) await onUpdateComplete();
    } catch (error: unknown) {
      console.error("An error occurred while creating the object: ", error);
    }
  }

  return (
    <div className={"bg-custom-white flex flex-col flex-1 overflow-auto p-4"}>
      <Form form={form} onSubmit={handleSubmit}>
        <InputField
          name="name"
          label="Name"
          rules={{
            required: true,
            validate: {
              required: isRequired,
            },
          }}
        />

        {!currentObject && (
          <InputField
            name="password"
            label="Password"
            type="password"
            rules={{
              required: true,
              validate: {
                required: isRequired,
              },
            }}
          />
        )}

        <InputField name="description" label="Description" />

        <RelationshipField
          name="member_of_groups"
          label="Groups"
          relationship={{
            name: "member_of_groups",
            peer: ACCOUNT_GROUP_OBJECT,
            cardinality: "many",
          }}
          schema={schema}
          options={groups.value}
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

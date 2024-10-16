import { Button } from "@/components/buttons/button-primitive";
import { NodeFormProps } from "@/components/form/node-form";
import { FormFieldValue } from "@/components/form/type";
import { getCurrentFieldValue } from "@/components/form/utils/getFieldDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/components/form/utils/mutations/getCreateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Form, FormSubmit } from "@/components/ui/form";
import { ACCOUNT_ROLE_OBJECT, GLOBAL_PERMISSION_OBJECT } from "@/config/constants";
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

import DropdownField from "@/components/form/fields/dropdown.field";
import InputField from "@/components/form/fields/input.field";
import RelationshipField from "@/components/form/fields/relationship.field";
import { getRelationshipDefaultValue } from "@/components/form/utils/getRelationshipDefaultValue";
import { isRequired } from "@/components/form/utils/validation";
import { useSchema } from "@/hooks/useSchema";

interface NumberPoolFormProps extends Pick<NodeFormProps, "onSuccess"> {
  currentObject?: Record<string, AttributeType | RelationshipType>;
  onCancel?: () => void;
  onUpdateComplete?: () => void;
}

export const GlobalPermissionForm = ({
  currentObject,
  onSuccess,
  onCancel,
  onUpdateComplete,
}: NumberPoolFormProps) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const { schema } = useSchema(GLOBAL_PERMISSION_OBJECT);

  const roles = getRelationshipDefaultValue({
    relationshipData: currentObject?.roles?.value,
  });

  const defaultValues = {
    name: getCurrentFieldValue("name", currentObject),
    action: getCurrentFieldValue("action", currentObject),
    decision: getCurrentFieldValue("decision", currentObject),
    roles,
  };

  const form = useForm<FieldValues>({
    defaultValues,
  });

  const actionOptions = schema?.attributes
    ?.find((attribute) => {
      return attribute.name === "action";
    })
    ?.choices?.map((choice) => {
      return {
        ...choice,
        value: choice.name,
      };
    });

  const decisionOptions = [
    {
      value: 1,
      label: "Deny",
    },
    {
      value: 6,
      label: "Allow",
    },
  ];

  async function handleSubmit(data: Record<string, FormFieldValue>) {
    try {
      const newObject = getCreateMutationFromFormDataOnly(data, currentObject);

      if (!Object.keys(newObject).length) {
        return;
      }

      const mutationString = currentObject
        ? updateObjectWithId({
            kind: GLOBAL_PERMISSION_OBJECT,
            data: stringifyWithoutQuotes({
              id: currentObject.id,
              ...newObject,
            }),
          })
        : createObject({
            kind: GLOBAL_PERMISSION_OBJECT,
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

      if (onSuccess) await onSuccess(result?.data?.[`${GLOBAL_PERMISSION_OBJECT}Create`]);
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

        <DropdownField
          name="action"
          label="Action"
          items={actionOptions}
          rules={{ required: true, validate: { required: isRequired } }}
        />

        <DropdownField
          name="decision"
          label="Decision"
          items={decisionOptions}
          rules={{ required: true, validate: { required: isRequired } }}
        />

        <RelationshipField
          name="roles"
          label="Roles"
          relationship={{
            name: "roles",
            peer: ACCOUNT_ROLE_OBJECT,
            cardinality: "many",
          }}
          options={roles.value}
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

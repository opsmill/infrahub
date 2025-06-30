import { ACCOUNT_ROLE_OBJECT, OBJECT_PERMISSION_OBJECT } from "@/config/constants";
import { currentBranchAtom } from "@/entities/branches/stores";
import { createObject } from "@/entities/nodes/api/createObject";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { NodeFormProps } from "@/shared/components/form/node-form";
import { FormFieldValue } from "@/shared/components/form/type";
import { getCurrentFieldValue } from "@/shared/components/form/utils/getFieldDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { FieldValues, useForm } from "react-hook-form";
import { toast } from "react-toastify";

import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import DropdownField from "@/shared/components/form/fields/dropdown.field";
import RelationshipManyField from "@/shared/components/form/fields/relationship-many.field";
import { NameSelect } from "@/shared/components/form/name-select";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { isRequired } from "@/shared/components/form/utils/validation";
import { objectDecisionOptions } from "../constants";

interface NumberPoolFormProps extends Pick<NodeFormProps, "onSuccess"> {
  currentObject?: Record<string, AttributeType | RelationshipType>;
  onCancel?: () => void;
  onUpdateComplete?: () => void;
}

export const ObjectPermissionForm = ({
  currentObject,
  onSuccess,
  onCancel,
  onUpdateComplete,
}: NumberPoolFormProps) => {
  const { schema } = useSchema(OBJECT_PERMISSION_OBJECT);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const roles = getRelationshipDefaultValue({
    relationshipData: currentObject?.roles?.value,
  });

  const defaultValues = {
    namespace: getCurrentFieldValue("namespace", currentObject) ?? DEFAULT_FORM_FIELD_VALUE,
    name: getCurrentFieldValue("name", currentObject) ?? DEFAULT_FORM_FIELD_VALUE,
    action: getCurrentFieldValue("action", currentObject) ?? DEFAULT_FORM_FIELD_VALUE,
    decision: getCurrentFieldValue("decision", currentObject) ?? DEFAULT_FORM_FIELD_VALUE,
    roles: roles ?? DEFAULT_FORM_FIELD_VALUE,
  };

  const form = useForm<FieldValues>({
    defaultValues,
  });

  const actionOptions = [
    {
      value: "any",
      label: "*",
    },
    {
      value: "view",
      label: "View",
    },
    {
      value: "create",
      label: "Create",
    },
    {
      value: "update",
      label: "Update",
    },
    {
      value: "delete",
      label: "Delete",
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
            kind: OBJECT_PERMISSION_OBJECT,
            data: stringifyWithoutQuotes({
              id: currentObject.id,
              ...newObject,
            }),
          })
        : createObject({
            kind: OBJECT_PERMISSION_OBJECT,
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

      if (currentObject) {
        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Object permission updated!"} />, {
          toastId: "alert-success-object-permission-updated",
        });
      } else {
        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Object permission created!"} />, {
          toastId: "alert-success-object-permission-created",
        });
      }

      if (onSuccess) await onSuccess(result?.data?.[`${OBJECT_PERMISSION_OBJECT}Create`]);
      if (onUpdateComplete) await onUpdateComplete();
    } catch (error: unknown) {
      console.error("An error occurred while creating the object: ", error);
    }
  }

  return (
    <div className={"bg-white flex flex-col flex-1 overflow-auto p-4"}>
      <Form form={form} onSubmit={handleSubmit}>
        <NameSelect />

        <DropdownField
          name="action"
          label="Action"
          items={actionOptions}
          rules={{ required: true, validate: { required: isRequired } }}
        />

        <DropdownField
          name="decision"
          label="Decision"
          description={
            schema?.attributes?.find((attribute) => attribute.name === "decision")?.description
          }
          items={objectDecisionOptions}
          rules={{ required: true, validate: { required: isRequired } }}
        />

        <RelationshipManyField
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

          <FormSubmit>Save</FormSubmit>
        </div>
      </Form>
    </div>
  );
};

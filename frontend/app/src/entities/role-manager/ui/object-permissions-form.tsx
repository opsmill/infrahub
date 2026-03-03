import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { type FieldValues, useForm } from "react-hook-form";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import DropdownField from "@/shared/components/form/fields/dropdown.field";
import RelationshipManyField from "@/shared/components/form/fields/relationships/relationship-many.field";
import { NameSelect } from "@/shared/components/form/name-select";
import type { NodeFormProps } from "@/shared/components/form/node-form";
import type { FormFieldValue } from "@/shared/components/form/type";
import { getCurrentFieldValue } from "@/shared/components/form/utils/getFieldDefaultValue";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { isRequired } from "@/shared/components/form/utils/validation";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { ACCOUNT_ROLE_OBJECT, OBJECT_PERMISSION_OBJECT } from "@/shared/config/constants";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import type { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { objectDecisionOptions } from "@/entities/role-manager/constants";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface ObjectPermissionFormProps {
  currentObject?: Record<string, AttributeType | RelationshipType>;
  onCancel?: () => void;
  onSuccess?: NodeFormProps["onSuccess"];
}

export const ObjectPermissionForm = ({
  currentObject,
  onSuccess,
  onCancel,
}: ObjectPermissionFormProps) => {
  const { schema } = useSchema(OBJECT_PERMISSION_OBJECT);
  const { currentBranch } = useCurrentBranch();
  const date = useAtomValue(datetimeAtom);
  const createObject = useCreateObjectMutation();

  const roles = getRelationshipDefaultValue({
    objectData: { roles: currentObject?.roles?.value },
    relationshipName: "roles",
  });

  const defaultValues = {
    namespace: getCurrentFieldValue("namespace", currentObject),
    name: getCurrentFieldValue("name", currentObject),
    action: getCurrentFieldValue("action", currentObject),
    decision: getCurrentFieldValue("decision", currentObject),
    roles,
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
    const newObject = getCreateMutationFromFormDataOnly(data, currentObject);

    if (!Object.keys(newObject).length) {
      return;
    }

    if (currentObject) {
      try {
        const result = await graphqlClient.mutate({
          mutation: gql(
            updateObjectWithId({
              kind: OBJECT_PERMISSION_OBJECT,
              data: stringifyWithoutQuotes({
                id: currentObject.id,
                ...newObject,
              }),
            })
          ),
          context: {
            branch: currentBranch.name,
            date,
          },
        });

        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Object permission updated!"} />, {
          toastId: "alert-success-object-permission-updated",
        });

        if (onSuccess) await onSuccess(result?.data?.[`${OBJECT_PERMISSION_OBJECT}Update`]);
      } catch (error: unknown) {
        console.error("An error occurred while creating the object: ", error);
      }
    } else {
      await createObject.mutateAsync(
        {
          objectKind: OBJECT_PERMISSION_OBJECT,
          data: newObject,
        },
        {
          onSuccess: async (newNode) => {
            toast(<Alert type={ALERT_TYPES.SUCCESS} message="Object permission created!" />, {
              toastId: "alert-success-object-permission-created",
            });
            if (onSuccess) await onSuccess(newNode);
          },
          onError: (error) => {
            console.error("An error occurred while creating the object: ", error);
          },
        }
      );
    }
  }

  return (
    <div className={"flex flex-1 flex-col overflow-auto bg-white p-4"}>
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
          defaultValue={roles}
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

import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { type FieldValues, useForm } from "react-hook-form";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import DropdownField from "@/shared/components/form/fields/dropdown.field";
import RelationshipManyField from "@/shared/components/form/fields/relationships/relationship-many.field";
import type { NodeFormProps } from "@/shared/components/form/node-form";
import type { FormFieldValue } from "@/shared/components/form/type";
import { getCurrentFieldValue } from "@/shared/components/form/utils/getFieldDefaultValue";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { isRequired } from "@/shared/components/form/utils/validation";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { ACCOUNT_ROLE_OBJECT, GLOBAL_PERMISSION_OBJECT } from "@/shared/config/constants";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import type { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { globalDecisionOptions } from "@/entities/role-manager/constants";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface GlobalPermissionFormProps {
  currentObject?: Record<string, AttributeType | RelationshipType>;
  onCancel?: () => void;
  onSuccess?: NodeFormProps["onSuccess"];
}

export const GlobalPermissionForm = ({
  currentObject,
  onSuccess,
  onCancel,
}: GlobalPermissionFormProps) => {
  const { currentBranch } = useCurrentBranch();
  const date = useAtomValue(datetimeAtom);
  const { schema } = useSchema(GLOBAL_PERMISSION_OBJECT);
  const createObject = useCreateObjectMutation();

  const roles = getRelationshipDefaultValue({
    objectData: { roles: currentObject?.roles?.value },
    relationshipName: "roles",
  });

  const defaultValues = {
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
              kind: GLOBAL_PERMISSION_OBJECT,
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

        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Global permission updated!"} />, {
          toastId: "alert-success-global-permission-updated",
        });

        if (onSuccess) await onSuccess(result?.data?.[`${GLOBAL_PERMISSION_OBJECT}Update`]);
      } catch (error: unknown) {
        console.error("An error occurred while creating the object: ", error);
      }
    } else {
      await createObject.mutateAsync(
        {
          objectKind: GLOBAL_PERMISSION_OBJECT,
          data: newObject,
        },
        {
          onSuccess: (newNode) => {
            toast(<Alert type={ALERT_TYPES.SUCCESS} message="Global permission created!" />, {
              toastId: "alert-success-global-permission-created",
            });

            if (onSuccess) onSuccess(newNode);
          },
          onError: (error) => {
            console.error("An error occurred while creating the object:", error);
          },
        }
      );
    }
  }

  return (
    <div className={"flex flex-1 flex-col overflow-auto bg-white p-4"}>
      <Form form={form} onSubmit={handleSubmit}>
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
          items={globalDecisionOptions}
          rules={{ required: true, validate: { required: isRequired } }}
        />

        <RelationshipManyField
          name="roles"
          label="Roles"
          defaultValue={roles}
          relationship={{
            name: "roles",
            peer: ACCOUNT_ROLE_OBJECT,
            cardinality: "many",
          }}
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

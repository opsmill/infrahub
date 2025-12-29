import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { type FieldValues, useForm } from "react-hook-form";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { LabelFormField } from "@/shared/components/form/fields/common";
import InputField from "@/shared/components/form/fields/input.field";
import RelationshipManyField from "@/shared/components/form/fields/relationships/relationship-many.field";
import type { NodeFormProps } from "@/shared/components/form/node-form";
import type { FormFieldValue } from "@/shared/components/form/type";
import { getCurrentFieldValue } from "@/shared/components/form/utils/getFieldDefaultValue";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { updateRelationshipFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { isRequired } from "@/shared/components/form/utils/validation";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormField, FormInput, FormSubmit } from "@/shared/components/ui/form";
import { ACCOUNT_GROUP_OBJECT, ACCOUNT_ROLE_OBJECT } from "@/shared/config/constants";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import type { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";
import { PermissionCombobox } from "@/entities/role-manager/ui/permission-combobox";

interface AccountRoleFormProps {
  currentObject?: Record<string, AttributeType | RelationshipType>;
  onCancel?: () => void;
  onSuccess?: NodeFormProps["onSuccess"];
}

export const AccountRoleForm = ({ currentObject, onCancel, onSuccess }: AccountRoleFormProps) => {
  const { currentBranch } = useCurrentBranch();
  const date = useAtomValue(datetimeAtom);
  const createObject = useCreateObjectMutation();

  const groups = getRelationshipDefaultValue({
    relationshipData: currentObject?.groups?.value,
    relationshipName: "groups",
  });

  const permissions = getRelationshipDefaultValue({
    relationshipData: currentObject?.permissions?.value,
    relationshipName: "identifier",
  });

  const defaultValues = {
    name: getCurrentFieldValue("name", currentObject),
    groups,
    permissions,
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

      if (currentObject) {
        const result = await graphqlClient.mutate({
          mutation: gql(
            updateObjectWithId({
              kind: ACCOUNT_ROLE_OBJECT,
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

        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Role updated!"} />, {
          toastId: "alert-success-role-updated",
        });

        if (onSuccess) await onSuccess(result?.data?.[`${ACCOUNT_ROLE_OBJECT}Update`]);
      } else {
        await createObject.mutateAsync(
          {
            objectKind: ACCOUNT_ROLE_OBJECT,
            data: newObject,
          },
          {
            onSuccess: async (newNode) => {
              toast(<Alert type={ALERT_TYPES.SUCCESS} message="Role created!" />, {
                toastId: "alert-success-role-created",
              });
              if (onSuccess) await onSuccess(newNode);
            },
            onError: (error) => {
              console.error("An error occurred while creating the object:", error);
            },
          }
        );
      }
    } catch (error: unknown) {
      console.error("An error occurred while creating the object: ", error);
    }
  }

  return (
    <div className={"flex flex-1 flex-col overflow-auto bg-white p-4"}>
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

        <RelationshipManyField
          name="groups"
          label="Groups"
          relationship={{
            name: "groups",
            peer: ACCOUNT_GROUP_OBJECT,
            cardinality: "many",
          }}
          defaultValue={groups}
        />

        <FormField
          name="permissions"
          render={({ field }) => {
            const fieldData = field.value;
            return (
              <div className="flex flex-col gap-2">
                <LabelFormField label="Permissions" fieldData={fieldData} />

                <FormInput>
                  <PermissionCombobox
                    {...field}
                    value={fieldData.value}
                    onChange={(newValue) => {
                      field.onChange(
                        updateRelationshipFieldValue(
                          newValue.length > 0 ? newValue : null,
                          permissions
                        )
                      );
                    }}
                  />
                </FormInput>
              </div>
            );
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

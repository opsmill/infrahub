import { ACCOUNT_GROUP_OBJECT, ACCOUNT_ROLE_OBJECT } from "@/config/constants";
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
import { Form, FormField, FormInput, FormSubmit } from "@/shared/components/ui/form";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { FieldValues, useForm } from "react-hook-form";
import { toast } from "react-toastify";

import { PermissionCombobox } from "@/entities/role-manager/ui/permission-combobox";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField } from "@/shared/components/form/fields/common";
import InputField from "@/shared/components/form/fields/input.field";
import RelationshipManyField from "@/shared/components/form/fields/relationship-many.field";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { updateRelationshipFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { isRequired } from "@/shared/components/form/utils/validation";

interface NumberPoolFormProps extends Pick<NodeFormProps, "onSuccess"> {
  currentObject?: Record<string, AttributeType | RelationshipType>;
  onCancel?: () => void;
  onUpdateComplete?: () => void;
}

export const AccountRoleForm = ({
  currentObject,
  onSuccess,
  onCancel,
  onUpdateComplete,
}: NumberPoolFormProps) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const groups = getRelationshipDefaultValue({
    relationshipData: currentObject?.groups?.value,
  });

  const permissions = getRelationshipDefaultValue({
    relationshipData: currentObject?.permissions?.value,
    relationshipName: "identifier",
  });

  const defaultValues = {
    name: getCurrentFieldValue("name", currentObject) ?? DEFAULT_FORM_FIELD_VALUE,
    groups: groups ?? DEFAULT_FORM_FIELD_VALUE,
    permissions: permissions ?? DEFAULT_FORM_FIELD_VALUE,
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
            kind: ACCOUNT_ROLE_OBJECT,
            data: stringifyWithoutQuotes({
              id: currentObject.id,
              ...newObject,
            }),
          })
        : createObject({
            kind: ACCOUNT_ROLE_OBJECT,
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
        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Role updated!"} />, {
          toastId: "alert-success-role-updated",
        });
      } else {
        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Role created!"} />, {
          toastId: "alert-success-role-created",
        });
      }

      if (onSuccess) await onSuccess(result?.data?.[`${ACCOUNT_ROLE_OBJECT}Create`]);
      if (onUpdateComplete) await onUpdateComplete();
    } catch (error: unknown) {
      console.error("An error occurred while creating the object: ", error);
    }
  }

  return (
    <div className={"bg-white flex flex-col flex-1 overflow-auto p-4"}>
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
          options={groups.value}
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
                      field.onChange(updateRelationshipFieldValue(newValue, permissions));
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

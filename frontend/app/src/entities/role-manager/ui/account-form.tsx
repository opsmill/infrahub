import { type FieldValues, useForm } from "react-hook-form";
import { toast } from "react-toastify";

import InputField from "@/shared/components/form/fields/input.field";
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
import { ACCOUNT_GROUP_OBJECT, ACCOUNT_OBJECT } from "@/shared/config/constants";

import type { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface AccountFormProps {
  currentObject?: Record<string, AttributeType | RelationshipType>;
  onCancel?: () => void;
  onSuccess?: NodeFormProps["onSuccess"];
}

export const AccountForm = ({ currentObject, onSuccess, onCancel }: AccountFormProps) => {
  const { schema } = useSchema(ACCOUNT_OBJECT);
  const createObject = useCreateObjectMutation();
  const updateObject = useUpdateObjectMutation();

  const memberDefaultValue = getRelationshipDefaultValue({
    objectData: { member_of_groups: currentObject?.member_of_groups?.value },
    relationshipName: "member_of_groups",
  });

  const defaultValues = {
    name: getCurrentFieldValue("name", currentObject),
    password: getCurrentFieldValue("password", currentObject),
    description: getCurrentFieldValue("description", currentObject),
    label: getCurrentFieldValue("label", currentObject),
    member_of_groups: memberDefaultValue,
  };

  const form = useForm<FieldValues>({
    defaultValues,
  });

  async function handleSubmit(data: Record<string, FormFieldValue>) {
    const newObject = getCreateMutationFromFormDataOnly(data, currentObject);

    if (!Object.keys(newObject).length) {
      return;
    }

    if (currentObject) {
      await updateObject.mutateAsync(
        {
          objectKind: ACCOUNT_OBJECT,
          data: {
            id: currentObject.id,
            ...newObject,
          },
        },
        {
          onSuccess: async (updatedNode) => {
            toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Account updated!"} />, {
              toastId: "alert-success-account-updated",
            });
            if (onSuccess) await onSuccess(updatedNode);
          },
          onError: (error) => {
            console.error("An error occurred while updating the object: ", error);
          },
        }
      );
    } else {
      await createObject.mutateAsync(
        {
          objectKind: ACCOUNT_OBJECT,
          data: newObject,
        },
        {
          onSuccess: async (newNode) => {
            toast(<Alert type={ALERT_TYPES.SUCCESS} message="Account created!" />, {
              toastId: "alert-success-account-created",
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

        <RelationshipManyField
          name="member_of_groups"
          label="Groups"
          relationship={{
            name: "member_of_groups",
            peer: ACCOUNT_GROUP_OBJECT,
            cardinality: "many",
          }}
          schema={schema}
          defaultValue={memberDefaultValue}
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

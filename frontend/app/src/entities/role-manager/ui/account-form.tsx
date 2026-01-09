import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { type FieldValues, useForm } from "react-hook-form";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import InputField from "@/shared/components/form/fields/input.field";
import RelationshipManyField from "@/shared/components/form/fields/relationships/relationship-many.field";
import type { NodeFormProps } from "@/shared/components/form/node-form";
import type { FormFieldValue } from "@/shared/components/form/type";
import { getCurrentFieldValue } from "@/shared/components/form/utils/getFieldDefaultValue";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { isRequired } from "@/shared/components/form/utils/validation";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { ACCOUNT_GROUP_OBJECT, ACCOUNT_OBJECT } from "@/shared/config/constants";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import type { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface AccountFormProps {
  currentObject?: Record<string, AttributeType | RelationshipType>;
  onCancel?: () => void;
  onSuccess?: NodeFormProps["onSuccess"];
}

export const AccountForm = ({ currentObject, onSuccess, onCancel }: AccountFormProps) => {
  const { currentBranch } = useCurrentBranch();
  const date = useAtomValue(datetimeAtom);
  const { schema } = useSchema(ACCOUNT_OBJECT);
  const createObject = useCreateObjectMutation();

  const memberDefaultValue = getRelationshipDefaultValue({
    relationshipData: currentObject?.member_of_groups?.value,
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
      try {
        const result = await graphqlClient.mutate({
          mutation: gql(
            updateObjectWithId({
              kind: ACCOUNT_OBJECT,
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

        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Account updated!"} />, {
          toastId: "alert-success-account-updated",
        });

        if (onSuccess) await onSuccess(result?.data?.[`${ACCOUNT_OBJECT}Update`]);
      } catch (error: unknown) {
        console.error("An error occurred while updating the object: ", error);
      }
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

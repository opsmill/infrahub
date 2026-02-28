import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { type FieldValues, useForm } from "react-hook-form";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import DropdownField from "@/shared/components/form/fields/dropdown.field";
import InputField from "@/shared/components/form/fields/input.field";
import RelationshipManyField from "@/shared/components/form/fields/relationships/relationship-many.field";
import type { NodeFormProps } from "@/shared/components/form/node-form";
import type { FormFieldValue } from "@/shared/components/form/type";
import { getCurrentFieldValue } from "@/shared/components/form/utils/getFieldDefaultValue";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { isRequired } from "@/shared/components/form/utils/validation";
import type { DropdownOption } from "@/shared/components/inputs/dropdown";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import {
  ACCOUNT_GROUP_OBJECT,
  ACCOUNT_OBJECT,
  ACCOUNT_ROLE_OBJECT,
} from "@/shared/config/constants";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import type { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface AccountGroupFormProps {
  currentObject?: Record<string, AttributeType | RelationshipType>;
  onCancel?: () => void;
  onSuccess?: NodeFormProps["onSuccess"];
}

export const AccountGroupForm = ({ currentObject, onSuccess, onCancel }: AccountGroupFormProps) => {
  const { currentBranch } = useCurrentBranch();
  const date = useAtomValue(datetimeAtom);
  const { schema } = useSchema(ACCOUNT_GROUP_OBJECT);
  const createObject = useCreateObjectMutation();

  const roles = getRelationshipDefaultValue({
    objectData: { roles: currentObject?.roles?.value },
    relationshipName: "roles",
  });

  const members = getRelationshipDefaultValue({
    objectData: { members: currentObject?.members?.value },
    relationshipName: "members",
  });

  const defaultValues = {
    name: getCurrentFieldValue("name", currentObject),
    description: getCurrentFieldValue("description", currentObject),
    label: getCurrentFieldValue("label", currentObject),
    group_type: getCurrentFieldValue("group_type", currentObject),
    roles,
    members,
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
              kind: ACCOUNT_GROUP_OBJECT,
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

        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Group updated!"} />, {
          toastId: "alert-success-group-updated",
        });

        if (onSuccess) await onSuccess(result?.data?.[`${ACCOUNT_GROUP_OBJECT}Update`]);
      } catch (error: unknown) {
        console.error("An error occurred while creating the object: ", error);
      }
    } else {
      await createObject.mutateAsync(
        {
          objectKind: ACCOUNT_GROUP_OBJECT,
          data: newObject,
        },
        {
          onSuccess: async (newNode) => {
            toast(<Alert type={ALERT_TYPES.SUCCESS} message="Group created!" />, {
              toastId: "alert-success-group-created",
            });
            if (onSuccess) await onSuccess(newNode);
          },
          onError: (error) => {
            console.error("An error occurred while creating the object:", error);
          },
        }
      );
    }
  }

  const typeOptions: DropdownOption[] =
    schema?.attributes
      ?.find((attribute) => attribute.name === "group_type")
      ?.enum?.map((data) => ({ value: data as string, label: data as string })) ?? [];

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

        <InputField name="description" label="Description" />

        <InputField name="label" label="Label" />

        <DropdownField name="group_type" label="Type" items={typeOptions} />

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

        <RelationshipManyField
          name="members"
          label="Members"
          relationship={{
            name: "members",
            peer: ACCOUNT_OBJECT,
            cardinality: "many",
          }}
          defaultValue={members}
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

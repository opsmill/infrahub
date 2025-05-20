import { createObject } from "@/entities/nodes/api/createObject";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { NodeFormProps } from "@/shared/components/form/node-form";
import { DynamicDropdownFieldProps, FormFieldValue } from "@/shared/components/form/type";
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

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { DynamicInput } from "@/shared/components/form/dynamic-form";
import { LabelFormField } from "@/shared/components/form/fields/common";
import DropdownField from "@/shared/components/form/fields/dropdown.field";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { DropdownOption } from "@/shared/components/inputs/dropdown";
import { Skeleton } from "@/shared/components/skeleton";
import { useParams } from "react-router";
import { NODE_TRIGGER_ATTRIBUTE_MATCH } from "../constants";

interface NodeAttributeMatchFormProps extends NodeFormProps {}

export const NodeAttributeMatchForm = ({
  currentObject,
  objectTemplate,
  isUpdate,
  onSuccess,
  onCancel,
  schema,
  ...props
}: NodeAttributeMatchFormProps) => {
  const { currentBranch } = useCurrentBranch();
  const date = useAtomValue(datetimeAtom);
  const { objectid } = useParams();
  const { data, isPending } = useGetObject({ objectSchema: schema, objectId: objectid });

  const schemaFields = getFormFieldsFromSchema({
    ...props,
    schema,
    initialObject: currentObject,
    isUpdate,
  });

  const attributeField = schemaFields.find((field) => {
    return field.name === "attribute_name";
  }) as DynamicDropdownFieldProps;

  const fields = schemaFields.filter((field) => {
    return field.name !== "attribute_name";
  });

  const defaultValues = {
    attribute_name: getCurrentFieldValue("attribute_name", {
      attribute_name: currentObject?.attribute_name as AttributeType,
    }),
    value: getCurrentFieldValue("value", {
      value: currentObject?.value as AttributeType,
    }),
    value_previous: getCurrentFieldValue("value_previous", {
      value_previous: currentObject?.value_previous as AttributeType,
    }),
    value_match: getCurrentFieldValue("value_match", {
      value_match: currentObject?.value_match as AttributeType,
    }),
    member_of_group: getRelationshipDefaultValue({
      relationshipData: currentObject?.member_of_group as RelationshipType | undefined,
      relationshipName: "member_of_group",
      objectTemplate,
    }),
    trigger: getRelationshipDefaultValue({
      relationshipData: currentObject?.trigger as RelationshipType | undefined,
      relationshipName: "trigger",
      objectTemplate,
    }),
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
            kind: NODE_TRIGGER_ATTRIBUTE_MATCH,
            data: stringifyWithoutQuotes({
              id: currentObject.id,
              ...newObject,
            }),
          })
        : createObject({
            kind: NODE_TRIGGER_ATTRIBUTE_MATCH,
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
          branch: currentBranch.name,
          date,
        },
      });

      if (currentObject) {
        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Node attribute match updated!"} />, {
          toastId: "alert-success-node-attribute-match-updated",
        });
      } else {
        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Node attribute match created!"} />, {
          toastId: "alert-success-node-attribute-match-created",
        });
      }

      if (onSuccess)
        await onSuccess(
          result?.data?.[`${NODE_TRIGGER_ATTRIBUTE_MATCH}${currentObject ? "Update" : "Create"}`]
        );
    } catch (error: unknown) {
      console.error("An error occurred while creating the object: ", error);
    }
  }

  return (
    <div className={"bg-white flex flex-col flex-1 overflow-auto p-4"}>
      <Form form={form} onSubmit={handleSubmit}>
        <NodeAttributeField
          field={attributeField}
          kind={data?.node_kind?.value}
          isLoading={isPending}
        />

        {fields.map((field) => {
          return <DynamicInput key={field.name} {...field} />;
        })}

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

interface NodeAttributeFieldProps {
  kind?: string;
  isLoading?: boolean;
  field?: DynamicDropdownFieldProps;
}

const NodeAttributeField = ({ field, kind, isLoading }: NodeAttributeFieldProps) => {
  const { schema } = useSchema(kind);

  if (isLoading) {
    return (
      <div className="space-y-2">
        <LabelFormField
          label={"Attribute Name"}
          required={!!field?.rules?.required}
          description={field?.description}
        />

        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  const attributeOptions: Array<DropdownOption> =
    schema?.attributes?.map((attribute) => {
      return {
        value: attribute.name,
        label: attribute.label ?? attribute.name,
      };
    }) ?? [];

  return <DropdownField {...field} name="attribute_name" items={attributeOptions} />;
};

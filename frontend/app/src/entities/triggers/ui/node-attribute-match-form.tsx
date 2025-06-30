import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { createObject } from "@/entities/nodes/api/createObject";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { NODE_TRIGGER_ATTRIBUTE_MATCH, NODE_TRIGGER_RULE } from "@/entities/triggers/constants";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { DynamicInput } from "@/shared/components/form/dynamic-form";
import { LabelFormField } from "@/shared/components/form/fields/common";
import DropdownField from "@/shared/components/form/fields/dropdown.field";
import { NodeFormProps } from "@/shared/components/form/node-form";
import {
  DynamicDropdownFieldProps,
  FormAttributeValue,
  FormFieldValue,
} from "@/shared/components/form/type";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";

import { getCurrentFieldValue } from "@/shared/components/form/utils/getFieldDefaultValue";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { DropdownOption } from "@/shared/components/inputs/dropdown";
import { Skeleton } from "@/shared/components/skeleton";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { FieldValues, useForm, useFormContext } from "react-hook-form";
import { toast } from "react-toastify";

interface NodeAttributeMatchFormProps extends NodeFormProps {}

export const NodeAttributeMatchForm = ({
  currentObject,
  objectTemplate,
  isUpdate,
  onSuccess,
  onCancel,
  ...props
}: NodeAttributeMatchFormProps) => {
  const { currentBranch } = useCurrentBranch();
  const date = useAtomValue(datetimeAtom);
  const { parentData, parentSchema } = useCurrentFormContext();

  const schemaFields = getFormFieldsFromSchema({
    ...props,
    initialObject: currentObject,
    isUpdate,
    parentData,
    parentSchema,
  });

  const attributeField = schemaFields.find((field) => {
    return field.name === "attribute_name";
  }) as DynamicDropdownFieldProps;

  const fields = schemaFields.filter((field) => {
    return field.name !== "attribute_name";
  });

  const defaultValues = {
    attribute_name:
      getCurrentFieldValue("attribute_name", {
        attribute_name: currentObject?.attribute_name as AttributeType,
      }) ?? DEFAULT_FORM_FIELD_VALUE,
    value:
      getCurrentFieldValue("value", {
        value: currentObject?.value as AttributeType,
      }) ?? DEFAULT_FORM_FIELD_VALUE,
    value_previous:
      getCurrentFieldValue("value_previous", {
        value_previous: currentObject?.value_previous as AttributeType,
      }) ?? DEFAULT_FORM_FIELD_VALUE,
    value_match:
      getCurrentFieldValue("value_match", {
        value_match: currentObject?.value_match as AttributeType,
      }) ?? DEFAULT_FORM_FIELD_VALUE,
    member_of_group:
      getRelationshipDefaultValue({
        relationshipData: currentObject?.member_of_group as RelationshipType | undefined,
        relationshipName: "member_of_group",
        objectTemplate,
      }) ?? DEFAULT_FORM_FIELD_VALUE,
    trigger:
      getRelationshipDefaultValue({
        relationshipData: currentObject?.trigger as RelationshipType | undefined,
        relationshipName: "trigger",
        objectTemplate,
        schema: props.schema,
        parentData,
        parentSchema,
      }) ?? DEFAULT_FORM_FIELD_VALUE,
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

      const mutationString = currentObject?.id
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

      if (currentObject?.id) {
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
        <NodeAttributeField field={attributeField} />

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
  field?: DynamicDropdownFieldProps;
}

const NodeAttributeField = ({ field }: NodeAttributeFieldProps) => {
  const form = useFormContext();

  const { schema } = useSchema(NODE_TRIGGER_RULE);
  const selectedTriggerField: FormAttributeValue = form.watch("trigger");

  const { data, isPending } = useGetObject({
    objectId: selectedTriggerField.value?.id,
    objectSchema: schema,
  });

  const { schema: peerSchema } = useSchema(data?.node_kind?.value);

  if (isPending) {
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
    peerSchema?.attributes?.map((attribute) => {
      return {
        value: attribute.name,
        label: attribute.label ?? attribute.name,
      };
    }) ?? [];

  return (
    <DropdownField
      {...field}
      key={data?.node_kind?.value}
      name="attribute_name"
      items={attributeOptions}
    />
  );
};

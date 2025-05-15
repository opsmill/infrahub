import { currentBranchAtom } from "@/entities/branches/stores";
import { createObject } from "@/entities/nodes/api/createObject";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
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
import { DynamicInput } from "@/shared/components/form/dynamic-form";
import DropdownField from "@/shared/components/form/fields/dropdown.field";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { isRequired } from "@/shared/components/form/utils/validation";
import { DropdownOption } from "@/shared/components/inputs/dropdown";
import { useParams } from "react-router";
import { NODE_TRIGGER_ATTRIBUTE_MATCH } from "../constants";

interface NodeAttributeMatchFormProps extends NodeFormProps {}

export const NodeAttributeMatchForm = ({
  currentObject,
  isUpdate,
  onSuccess,
  onCancel,
  ...props
}: NodeAttributeMatchFormProps) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const schemaFields = getFormFieldsFromSchema({
    ...props,
    initialObject: currentObject,
    isUpdate,
  });

  const fields = schemaFields.filter((field) => {
    return field.name !== "attribute_name";
  });

  const defaultValues = {
    action: getCurrentFieldValue("action", currentObject),
    decision: getCurrentFieldValue("decision", currentObject),
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
          branch: branch?.name,
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
        <NodeAttributeField />

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

const NodeAttributeField = () => {
  const { objectKind } = useParams();
  const { schema } = useSchema(objectKind);

  const objectAttributes = schema?.attributes;

  const attributeOptions: Array<DropdownOption> =
    objectAttributes?.map((attribute) => {
      return {
        value: attribute.name,
        label: attribute.label ?? attribute.name,
      };
    }) ?? [];

  return (
    <DropdownField
      defaultValue={DEFAULT_FORM_FIELD_VALUE}
      rules={{ validate: { required: isRequired } }}
      name="attribute_name"
      label="Attribute Name"
      items={attributeOptions}
    />
  );
};

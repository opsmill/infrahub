import { Button } from "@/components/buttons/button-primitive";
import DropdownField from "@/components/form/fields/dropdown.field";
import InputField from "@/components/form/fields/input.field";
import NumberField from "@/components/form/fields/number.field";
import { NodeFormProps } from "@/components/form/node-form";
import { FormFieldValue } from "@/components/form/type";
import { getCurrentFieldValue } from "@/components/form/utils/getFieldDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/components/form/utils/mutations/getCreateMutationFromFormData";
import { SelectOption } from "@/components/inputs/select";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { Form, FormSubmit } from "@/components/ui/form";
import { NUMBER_POOL_OBJECT } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { createObject } from "@/graphql/mutations/objects/createObject";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { useFormValues } from "@/hooks/useFormValues";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { schemaState } from "@/state/atoms/schema.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { AttributeType, RelationshipType } from "@/utils/getObjectItemDisplayValue";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useEffect } from "react";
import { FieldValues, useForm, useFormContext } from "react-hook-form";
import { toast } from "react-toastify";

interface NumberPoolFormProps extends Pick<NodeFormProps, "onSuccess"> {
  currentObject?: Record<string, AttributeType | RelationshipType>;
  onCancel?: () => void;
  onUpdateComplete?: () => void;
}

export const NumberPoolForm = ({
  currentObject,
  onSuccess,
  onCancel,
  onUpdateComplete,
}: NumberPoolFormProps) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const defaultValues = {
    name: getCurrentFieldValue("name", currentObject),
    description: getCurrentFieldValue("description", currentObject),
    node: getCurrentFieldValue("node", currentObject),
    node_attribute: getCurrentFieldValue("node_attribute", currentObject),
    start_range: getCurrentFieldValue("start_range", currentObject),
    end_range: getCurrentFieldValue("end_range", currentObject),
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
            kind: NUMBER_POOL_OBJECT,
            data: stringifyWithoutQuotes({
              id: currentObject.id,
              ...newObject,
            }),
          })
        : createObject({
            kind: NUMBER_POOL_OBJECT,
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

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Number pool created"} />, {
        toastId: "alert-success-number-pool-created",
      });

      if (onSuccess) await onSuccess(result?.data?.[`${NUMBER_POOL_OBJECT}Create`]);
      if (onUpdateComplete) await onUpdateComplete();
    } catch (error: unknown) {
      console.error("An error occurred while creating the object: ", error);
    }
  }

  return (
    <div className={"bg-custom-white flex flex-col flex-1 overflow-auto p-4"}>
      <Form form={form} onSubmit={handleSubmit}>
        <InputField name="name" label="Name" rules={{ required: true }} />
        <InputField name="description" label="Description" />
        {!currentObject && <NodeAttributesSelects />}
        <NumberField
          name="start_range"
          label="Start range"
          description="The start range for the pool"
          rules={{ required: true }}
        />
        <NumberField
          name="end_range"
          label="End range"
          description="The end range for the pool"
          rules={{ required: true }}
        />
        <div className="text-right">
          {onCancel && (
            <Button variant="outline" className="mr-2" onClick={onCancel}>
              Cancel
            </Button>
          )}

          <FormSubmit>{currentObject ? "Update" : "Create"}</FormSubmit>
        </div>
      </Form>
    </div>
  );
};

const NodeAttributesSelects = () => {
  const schemaList = useAtomValue(schemaState);

  const { resetField } = useFormContext();

  // Watch form value to rebuild 2nd select options
  const { node } = useFormValues();

  const availableSchemaList = schemaList?.filter(
    (schema) =>
      !!schema.attributes?.find((attribute) => attribute.kind === "Number" && !attribute.read_only)
  );

  const selectedNode = availableSchemaList.find((schema) => schema.kind === node?.value);
  const nodesOptions: SelectOption[] = availableSchemaList.map((schema) => ({
    id: schema.kind as string,
    name: schema.label as string,
  }));

  const attributesOptions: SelectOption[] = selectedNode?.attributes
    ? selectedNode.attributes
        ?.filter((attribute) => attribute.kind === "Number")
        ?.map((attribute) => ({ id: attribute.name as string, name: attribute.label as string }))
    : [];

  const relationshipsOptions: SelectOption[] = selectedNode?.relationships
    ? selectedNode.relationships
        ?.filter((relationship) => relationship.cardinality === "one")
        ?.map((relationship) => ({
          id: relationship.name as string,
          name: relationship.label as string,
        }))
    : [];

  useEffect(() => {
    resetField("node_attribute");
  }, [node?.value]);

  return (
    <>
      <DropdownField
        name="node"
        label="Node"
        description="The model of the object that requires integers to be allocated"
        rules={{ required: true }}
        items={nodesOptions}
      />
      <DropdownField
        name="node_attribute"
        label="Attribute"
        description="The attribute of the selected model"
        rules={{ required: true }}
        items={attributesOptions}
      />
      <DropdownField
        name="unique_for"
        label="Unique for"
        description="Relationship to another model adding a uniqueness constraint the allocated integer"
        items={relationshipsOptions}
      />
    </>
  );
};

import DropdownField from "@/components/form/fields/dropdown.field";
import InputField from "@/components/form/fields/input.field";
import { NodeFormProps } from "@/components/form/node-form";
import { FormFieldValue } from "@/components/form/type";
import { getCurrentFieldValue } from "@/components/form/utils/getFieldDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/components/form/utils/mutations/getCreateMutationFromFormData";
import { SelectOption } from "@/components/inputs/select";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { Form } from "@/components/ui/form";
import { NUMBER_POOL_OBJECT } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { createObject } from "@/graphql/mutations/objects/createObject";
import { useFormValues } from "@/hooks/useFormValues";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { schemaState } from "@/state/atoms/schema.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { AttributeType } from "@/utils/getObjectItemDisplayValue";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { FieldValues, useForm } from "react-hook-form";
import { toast } from "react-toastify";

interface NumberPoolFormProps extends Pick<NodeFormProps, "onSuccess"> {
  currentObject?: Record<string, AttributeType>;
}

export const NumberPoolForm = ({ onSuccess, currentObject }: NumberPoolFormProps) => {
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
      const newObject = getCreateMutationFromFormDataOnly(data);

      if (!Object.keys(newObject).length) {
        return;
      }

      const mutationString = createObject({
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
    } catch (error: unknown) {
      console.error("An error occurred while creating the object: ", error);
    }
  }

  return (
    <div className={"bg-custom-white flex flex-col flex-1 overflow-auto p-4"}>
      <Form form={form} onSubmit={handleSubmit}>
        <InputField name="name" label="Name" rules={{ required: true }} />
        <InputField name="description" label="Description" />
        <NodeAttributesSelects />
        <InputField
          name="start_range"
          label="Start range"
          description="The start range for the pool"
          rules={{ required: true }}
          type="number"
        />
        <InputField
          name="end_range"
          label="End range"
          description="The end range for the pool"
          rules={{ required: true }}
          type="number"
        />
      </Form>
    </div>
  );
};

const NodeAttributesSelects = () => {
  const schemaList = useAtomValue(schemaState);

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
    </>
  );
};

import { Button } from "@/components/buttons/button-primitive";
import InputField from "@/components/form/fields/input.field";
import NumberField from "@/components/form/fields/number.field";
import { NodeFormProps } from "@/components/form/node-form";
import { FormAttributeValue, FormFieldValue } from "@/components/form/type";
import { getCurrentFieldValue } from "@/components/form/utils/getFieldDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/components/form/utils/mutations/getCreateMutationFromFormData";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { Form, FormField, FormInput, FormMessage, FormSubmit } from "@/components/ui/form";
import { NUMBER_POOL_OBJECT, SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { createObject } from "@/graphql/mutations/objects/createObject";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { iNodeSchema, schemaState } from "@/state/atoms/schema.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { AttributeType, RelationshipType } from "@/utils/getObjectItemDisplayValue";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { FieldValues, useForm, useFormContext } from "react-hook-form";
import { toast } from "react-toastify";
import { LabelFormField } from "@/components/form/fields/common";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/components/ui/combobox3";
import { Badge } from "@/components/ui/badge";
import {
  NUMBER_POOL_NODE_ATTRIBUTE_FIELD,
  NUMBER_POOL_NODE_FIELD,
} from "@/screens/resource-manager/constants";
import { AttributeSchema } from "@/screens/schema/types";
import { isRequired } from "@/components/form/utils/validation";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";
import { DEFAULT_FORM_FIELD_VALUE } from "@/components/form/constants";

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
  const nodes = useAtomValue(schemaState);

  const form = useFormContext();
  const selectedNodeField: FormAttributeValue = form.watch(NUMBER_POOL_NODE_FIELD);
  const selectedNode = nodes.find((node) => node.kind === selectedNodeField?.value);

  const nodesWithNumberAttributes: Array<iNodeSchema> = nodes.filter((node) =>
    node.attributes?.some(
      (attribute) => attribute.kind === SCHEMA_ATTRIBUTE_KIND.NUMBER && !attribute.read_only
    )
  );

  const numberAttributeOptions: Array<AttributeSchema> =
    selectedNode?.attributes?.filter(
      (attribute) => attribute.kind === SCHEMA_ATTRIBUTE_KIND.NUMBER
    ) ?? [];

  useEffect(() => {
    if (numberAttributeOptions.length === 1) {
      form.setValue(
        NUMBER_POOL_NODE_ATTRIBUTE_FIELD,
        updateFormFieldValue(numberAttributeOptions[0].name, DEFAULT_FORM_FIELD_VALUE)
      );
    } else {
      form.resetField(NUMBER_POOL_NODE_ATTRIBUTE_FIELD);
    }
  }, [selectedNode?.kind]);

  return (
    <>
      <FormField
        name={NUMBER_POOL_NODE_FIELD}
        rules={{ validate: { required: isRequired } }}
        defaultValue={DEFAULT_FORM_FIELD_VALUE}
        render={({ field }) => {
          const [open, setOpen] = useState(false);

          return (
            <div className="flex flex-col gap-2">
              <LabelFormField
                label="Node"
                description="The model of the object that requires integers to be allocated"
                required
              />

              <Combobox open={open} onOpenChange={setOpen}>
                <FormInput>
                  <ComboboxTrigger>
                    {selectedNode && (
                      <div className="w-full flex justify-between">
                        {selectedNode.label} <Badge>{selectedNode.namespace}</Badge>
                      </div>
                    )}
                  </ComboboxTrigger>
                </FormInput>

                <ComboboxContent>
                  <ComboboxList>
                    {nodesWithNumberAttributes.map((node) => (
                      <ComboboxItem
                        key={node.id}
                        selectedValue={selectedNode?.kind}
                        value={node.kind!}
                        onSelect={() => {
                          const newValue = node.kind === selectedNode?.kind ? null : node.kind;
                          field.onChange(
                            updateFormFieldValue(newValue ?? null, DEFAULT_FORM_FIELD_VALUE)
                          );

                          setOpen(false);
                        }}>
                        <div className="w-full flex justify-between">
                          {node.label} <Badge>{node.namespace}</Badge>
                        </div>
                      </ComboboxItem>
                    ))}
                  </ComboboxList>
                </ComboboxContent>
              </Combobox>

              <FormMessage />
            </div>
          );
        }}
      />

      <FormField
        name={NUMBER_POOL_NODE_ATTRIBUTE_FIELD}
        rules={{ validate: { required: isRequired } }}
        defaultValue={DEFAULT_FORM_FIELD_VALUE}
        render={({ field }) => {
          const [open, setOpen] = useState(false);
          const selectedAttribute: FormFieldValue = field.value;

          return (
            <div className="flex flex-col gap-2">
              <LabelFormField
                label="Number Attribute"
                description="The number attribute of the selected model"
                required
              />

              <Combobox open={open} onOpenChange={setOpen}>
                <FormInput>
                  <ComboboxTrigger disabled={!selectedNode}>
                    {
                      numberAttributeOptions.find(
                        (attribute) => attribute.name === selectedAttribute?.value
                      )?.label
                    }
                  </ComboboxTrigger>
                </FormInput>

                <ComboboxContent>
                  <ComboboxList>
                    {numberAttributeOptions.map((attribute) => (
                      <ComboboxItem
                        key={attribute.id}
                        selectedValue={selectedAttribute?.value}
                        value={attribute.name}
                        onSelect={() => {
                          const newValue =
                            attribute.name === selectedNode?.name ? null : attribute.name;
                          field.onChange(updateFormFieldValue(newValue, DEFAULT_FORM_FIELD_VALUE));
                          setOpen(false);
                        }}>
                        {attribute.label}
                      </ComboboxItem>
                    ))}
                  </ComboboxList>
                </ComboboxContent>
              </Combobox>

              <FormMessage />
            </div>
          );
        }}
      />
    </>
  );
};

import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { type FieldValues, useForm, useFormContext } from "react-hook-form";
import { toast } from "react-toastify";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField } from "@/shared/components/form/fields/common";
import InputField from "@/shared/components/form/fields/input.field";
import NumberField from "@/shared/components/form/fields/number.field";
import type { ObjectFormProps } from "@/shared/components/form/object-form";
import type { FormAttributeValue, FormFieldValue } from "@/shared/components/form/type";
import { getCurrentFieldValue } from "@/shared/components/form/utils/getFieldDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { isRequired } from "@/shared/components/form/utils/validation";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { Form, FormField, FormInput, FormMessage, FormSubmit } from "@/shared/components/ui/form";
import { NUMBER_POOL_OBJECT } from "@/shared/config/constants";

import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import {
  NUMBER_POOL_NODE_ATTRIBUTE_FIELD,
  NUMBER_POOL_NODE_FIELD,
} from "@/entities/resource-manager/constants";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { AttributeSchema, ModelSchema } from "@/entities/schema/types";

interface NumberPoolFormProps {
  currentObject?: ObjectFormProps["currentObject"];
  onCancel?: ObjectFormProps["onCancel"];
  onSuccess?: ObjectFormProps["onSuccess"];
}

export const NumberPoolForm = ({ currentObject, onSuccess, onCancel }: NumberPoolFormProps) => {
  const createObject = useCreateObjectMutation();
  const updateObject = useUpdateObjectMutation();

  const defaultValues = {
    name: getCurrentFieldValue("name", currentObject) ?? DEFAULT_FORM_FIELD_VALUE,
    description: getCurrentFieldValue("description", currentObject) ?? DEFAULT_FORM_FIELD_VALUE,
    node: getCurrentFieldValue("node", currentObject) ?? DEFAULT_FORM_FIELD_VALUE,
    node_attribute:
      getCurrentFieldValue("node_attribute", currentObject) ?? DEFAULT_FORM_FIELD_VALUE,
    start_range: getCurrentFieldValue("start_range", currentObject) ?? DEFAULT_FORM_FIELD_VALUE,
    end_range: getCurrentFieldValue("end_range", currentObject) ?? DEFAULT_FORM_FIELD_VALUE,
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
          objectKind: NUMBER_POOL_OBJECT,
          data: {
            id: currentObject.id,
            ...newObject,
          },
        },
        {
          onSuccess: async (updatedNode) => {
            toast(<Alert type={ALERT_TYPES.SUCCESS} message="Number pool updated" />, {
              toastId: "alert-success-number-pool-update",
            });
            if (onSuccess) await onSuccess(updatedNode);
          },
          onError: (error) => {
            console.error("An error occurred while creating the object: ", error);
          },
        }
      );
    } else {
      await createObject.mutateAsync(
        {
          objectKind: NUMBER_POOL_OBJECT,
          data: newObject,
        },
        {
          onSuccess: async (newNode) => {
            toast(<Alert type={ALERT_TYPES.SUCCESS} message="Number pool created" />, {
              toastId: "alert-success-number-pool-create",
            });

            if (onSuccess) await onSuccess(newNode);
          },
          onError: async (error: unknown) => {
            console.error("An error occurred while creating the object: ", error);
          },
        }
      );
    }
  }

  return (
    <div className={"flex flex-1 flex-col overflow-auto bg-white p-4"}>
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

          <FormSubmit>Save</FormSubmit>
        </div>
      </Form>
    </div>
  );
};

const NodeAttributesSelects = () => {
  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);

  const options = [...generics, ...nodes];

  const form = useFormContext();
  const selectedNodeField: FormAttributeValue = form.watch(NUMBER_POOL_NODE_FIELD);
  const selectedNode = options.find((node) => node.kind === selectedNodeField?.value);

  const nodesWithNumberAttributes: Array<ModelSchema> = options.filter((node) =>
    node.attributes?.some(
      (attribute) => attribute.kind === ATTRIBUTE_KIND.NUMBER && !attribute.read_only
    )
  );

  const numberAttributeOptions: Array<AttributeSchema> =
    selectedNode?.attributes?.filter((attribute) => attribute.kind === ATTRIBUTE_KIND.NUMBER) ?? [];

  useEffect(() => {
    const firstAttribute = numberAttributeOptions[0];
    if (firstAttribute) {
      form.setValue(
        NUMBER_POOL_NODE_ATTRIBUTE_FIELD,
        updateFormFieldValue(firstAttribute.name, DEFAULT_FORM_FIELD_VALUE)
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
                      <div className="flex w-full justify-between">
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
                        keywords={[node.label as string]}
                        onSelect={() => {
                          const newValue = node.kind === selectedNode?.kind ? null : node.kind;
                          field.onChange(
                            updateFormFieldValue(newValue ?? null, DEFAULT_FORM_FIELD_VALUE)
                          );

                          setOpen(false);
                        }}
                      >
                        <div className="flex w-full justify-between">
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
                        selectedValue={selectedAttribute?.value?.toString()}
                        value={attribute.name}
                        keywords={[attribute.label as string]}
                        onSelect={() => {
                          const newValue =
                            attribute.name === selectedNode?.name ? null : attribute.name;
                          field.onChange(updateFormFieldValue(newValue, DEFAULT_FORM_FIELD_VALUE));
                          setOpen(false);
                        }}
                      >
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

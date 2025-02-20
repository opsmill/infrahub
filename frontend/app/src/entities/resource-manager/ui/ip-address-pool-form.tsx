import { NUMBER_POOL_OBJECT } from "@/config/constants";
import { useAuth } from "@/entities/authentication/ui/useAuth";
import { currentBranchAtom } from "@/entities/branches/stores";
import { IP_ADDRESS_GENERIC } from "@/entities/ipam/constants";
import { createObject } from "@/entities/nodes/api/createObject";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useSchema } from "@/entities/schema/hooks/useSchema";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField } from "@/shared/components/form/fields/common";
import InputField from "@/shared/components/form/fields/input.field";
import NumberField from "@/shared/components/form/fields/number.field";
import RelationshipManyField from "@/shared/components/form/fields/relationship-many.field";
import RelationshipField from "@/shared/components/form/fields/relationship.field";
import { NodeFormProps } from "@/shared/components/form/node-form";
import { FormAttributeValue, FormFieldValue } from "@/shared/components/form/type";
import { getCurrentFieldValue } from "@/shared/components/form/utils/getFieldDefaultValue";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { isRequired } from "@/shared/components/form/utils/validation";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { Form, FormField, FormInput, FormSubmit } from "@/shared/components/ui/form";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { FieldValues, useForm } from "react-hook-form";
import { toast } from "react-toastify";
import { IP_ADDRESS_POOL } from "../constants";

const ADDRESS_DEFAULT_TYPE_FIELD_NAME = "default_address_type";

interface IpAddressPoolFormProps extends Pick<NodeFormProps, "onSuccess"> {
  currentObject?: Record<string, AttributeType | RelationshipType>;
  onCancel?: () => void;
  onUpdateComplete?: () => void;
}

export const IpAddressPoolForm = ({
  currentObject,
  onSuccess,
  onCancel,
  onUpdateComplete,
}: IpAddressPoolFormProps) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const { schema } = useSchema(IP_ADDRESS_POOL);
  const auth = useAuth();

  const defaultValues = {
    name: getCurrentFieldValue("name", currentObject),
    description: getCurrentFieldValue("description", currentObject),
    default_prefix_length: getCurrentFieldValue("default_prefix_length", currentObject),
    resources: getRelationshipDefaultValue({
      relationshipData: currentObject?.resources,
    }),
    ip_namespace: getRelationshipDefaultValue({
      relationshipData: currentObject?.ip_namespace,
    }),
  };

  const fields = getFormFieldsFromSchema({
    schema,
    initialObject: currentObject,
    auth,
  });

  const form = useForm<FieldValues>({
    defaultValues,
  });

  const prefixLenghtAttribute = schema?.attributes?.find((attribute) => {
    return attribute.name === "default_prefix_length";
  });

  const resourcesRelatiosnhip = schema?.relationships?.find((relationship) => {
    return relationship.name === "resources";
  });

  const namespaceRelationship = schema?.relationships?.find((relationship) => {
    return relationship.name === "ip_namespace";
  });

  async function handleSubmit(data: Record<string, FormFieldValue>) {
    try {
      const newObject = getCreateMutationFromFormData(fields, data);

      if (!Object.keys(newObject).length) {
        return;
      }

      const mutationString = currentObject
        ? updateObjectWithId({
            kind: IP_ADDRESS_POOL,
            data: stringifyWithoutQuotes({
              id: currentObject.id,
              ...newObject,
            }),
          })
        : createObject({
            kind: IP_ADDRESS_POOL,
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
        <AddressTypesCombobox currentObject={currentObject} />
        <NumberField
          name="default_prefix_length"
          label={prefixLenghtAttribute?.label}
          description={prefixLenghtAttribute?.description}
        />
        <RelationshipManyField
          name="resources"
          type="relationship"
          label={resourcesRelatiosnhip?.label}
          description={resourcesRelatiosnhip?.description}
          relationship={{
            name: "resources",
            peer: "BuiltinIPPrefix",
            kind: "Attribute",
            label: "Resources",
          }}
          rules={{ required: true, validate: { required: isRequired } }}
        />
        <RelationshipField
          name="ip_namespace"
          type="relationship"
          label={namespaceRelationship?.label}
          description={namespaceRelationship?.description}
          relationship={{ peer: "BuiltinIPNamespace", name: "ip_namespace" }}
          rules={{ required: true, validate: { required: isRequired } }}
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

const AddressTypesCombobox = ({
  currentObject,
}: { currentObject?: Record<string, AttributeType | RelationshipType> }) => {
  const { schema } = useSchema(IP_ADDRESS_POOL);
  const schemaList = useAtomValue(nodeSchemasAtom);
  const { schema: genericSchema, isGeneric } = useSchema(IP_ADDRESS_GENERIC);
  const schemaKindName = useAtomValue(schemaKindLabelState);
  const [open, setOpen] = useState(false);

  const prefixTypeAttribute = schema?.attributes?.find((attribute) => {
    return attribute.name === ADDRESS_DEFAULT_TYPE_FIELD_NAME;
  });

  const items =
    (isGeneric &&
      genericSchema?.used_by?.map((kind) => {
        const currentSchema = schemaList.find((schema) => schema.kind === kind);

        return {
          value: kind,
          label: schemaKindName[kind],
          namespace: currentSchema?.namespace,
        };
      })) ??
    [];

  const currentValue = getCurrentFieldValue(ADDRESS_DEFAULT_TYPE_FIELD_NAME, currentObject);

  const defaultValue =
    (items[0] ?? currentValue)
      ? { source: { type: "user" }, value: items[0].value }
      : DEFAULT_FORM_FIELD_VALUE;

  return (
    <FormField
      name={ADDRESS_DEFAULT_TYPE_FIELD_NAME}
      rules={{ required: true, validate: { required: isRequired } }}
      defaultValue={defaultValue}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;

        return (
          <div className="flex flex-col gap-2">
            <LabelFormField
              label={prefixTypeAttribute?.label}
              required
              description={prefixTypeAttribute?.description}
              fieldData={fieldData}
            />

            <FormInput>
              <Combobox open={open} onOpenChange={setOpen}>
                <ComboboxTrigger data-testid="namespace-select">
                  {items.find((item) => item.value === fieldData?.value)?.label}
                </ComboboxTrigger>

                <ComboboxContent align="start" fitTriggerWidth={false}>
                  <ComboboxList className="max-w-md">
                    {items.map((item) => {
                      return (
                        <ComboboxItem
                          key={item.value}
                          value={item.value}
                          selectedValue={fieldData?.value}
                          onSelect={() => {
                            const newValue = fieldData?.value === item.value ? null : item.value;
                            field.onChange(
                              updateFormFieldValue(newValue ?? null, DEFAULT_FORM_FIELD_VALUE)
                            );
                            setOpen(false);
                          }}
                        >
                          <div className="overflow-hidden w-full flex items-center justify-between">
                            <div className="truncate font-semibold">{item.label}</div>
                            <Badge className="font-medium">{item.namespace}</Badge>
                          </div>
                        </ComboboxItem>
                      );
                    })}
                  </ComboboxList>
                </ComboboxContent>
              </Combobox>
            </FormInput>
          </div>
        );
      }}
    />
  );
};

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { IP_ADDRESS_GENERIC } from "@/entities/ipam/constants";
import { createObject } from "@/entities/nodes/api/createObject";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { NodeFormProps } from "@/shared/components/form/node-form";
import { DynamicSelectFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { useMemo } from "react";
import { toast } from "react-toastify";
import { capitalize } from "remeda";
import { IP_ADDRESS_POOL } from "../constants";

const ADDRESS_DEFAULT_TYPE_FIELD_NAME = "default_address_type";

interface IpAddressPoolFormProps extends NodeFormProps {}

export const IpAddressPoolForm = ({
  currentObject,
  isUpdate,
  onSubmit,
  onSuccess,
  ...props
}: IpAddressPoolFormProps) => {
  const { currentBranch } = useCurrentBranch();
  const { schema: genericAddressSchema, isGeneric } = useSchema(IP_ADDRESS_GENERIC);
  const { parentSchema, parentData } = useCurrentFormContext();

  const fields = useMemo(() => {
    const schemaFields = getFormFieldsFromSchema({
      ...props,
      initialObject: currentObject,
      isUpdate,
      parentSchema,
      parentData,
    });

    if (!genericAddressSchema || !isGeneric) return schemaFields;

    // Replace default_address_type (text) field with a select
    return schemaFields.map((field) => {
      if (field.name === ADDRESS_DEFAULT_TYPE_FIELD_NAME) {
        const items =
          genericAddressSchema.used_by?.map((kind) => {
            const { schema } = getSchema(kind);

            if (!schema) {
              return {
                key: kind,
                label: kind,
              };
            }

            return {
              key: kind,
              label: (
                <div className="flex items-center justify-between w-full">
                  <span>{schema.label}</span>
                  <span className="text-xs text-gray-500">{schema.namespace}</span>
                </div>
              ),
            };
          }) ?? [];

        const defaultValue =
          isUpdate && currentObject
            ? field.defaultValue
            : items.length === 1
              ? { source: { type: "user" }, value: items[0]?.key }
              : field.defaultValue;

        return {
          ...field,
          type: "select",
          items,
          defaultValue,
        } as DynamicSelectFieldProps;
      }
      return field;
    });
  }, [props.schema.kind, genericAddressSchema?.kind, currentObject, isUpdate]);

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
        context: { branch: currentBranch.name },
      });

      const operationType = isUpdate ? "update" : "create";
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={`IP address pool ${operationType}d`} />, {
        toastId: `alert-success-ip-prefix-pool-${operationType}`,
      });

      if (onSuccess) {
        const resultData = result?.data?.[`${IP_ADDRESS_POOL}${capitalize(operationType)}`];
        await onSuccess(resultData);
      }
    } catch (error: unknown) {
      console.error(
        `An error occurred while ${isUpdate ? "updating" : "creating"} the IP address pool:`,
        error
      );
    }
  }

  return (
    <DynamicForm
      fields={fields}
      onSubmit={(formData: Record<string, FormFieldValue>) =>
        onSubmit ? onSubmit({ formData, fields }) : handleSubmit(formData)
      }
      className="p-4 overflow-auto"
    />
  );
};

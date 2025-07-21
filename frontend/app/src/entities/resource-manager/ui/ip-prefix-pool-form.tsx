import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { createObject } from "@/entities/nodes/api/createObject";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import { IP_PREFIX_POOL } from "@/entities/resource-manager/constants";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { NodeFormProps } from "@/shared/components/form/node-form";
import { DynamicSelectFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { useMemo } from "react";
import { toast } from "react-toastify";

export interface IpPrefixPoolFormProps extends NodeFormProps {}

export function IpPrefixPoolForm({
  currentObject,
  isUpdate,
  onSuccess,
  onSubmit,
  ...props
}: IpPrefixPoolFormProps) {
  const { schema: genericPrefixSchema, isGeneric } = useSchema(IP_PREFIX_GENERIC);
  const { currentBranch } = useCurrentBranch();

  const fields = useMemo(() => {
    const schemaFields = getFormFieldsFromSchema({
      ...props,
      initialObject: currentObject,
      isUpdate,
    });

    if (!genericPrefixSchema || !isGeneric) return schemaFields;

    // Replace default_prefix_type (text) field with a select
    return schemaFields.map((field) => {
      if (field.name === "default_prefix_type") {
        const items =
          genericPrefixSchema.used_by?.map((kind) => {
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
  }, [props, genericPrefixSchema, isGeneric, currentObject, isUpdate]);

  async function handleSubmit(data: Record<string, FormFieldValue>) {
    try {
      const newObject = getCreateMutationFromFormData(fields, data, props.objectTemplate?.id);

      if (!Object.keys(newObject).length) {
        return;
      }

      const mutationString =
        isUpdate && currentObject
          ? updateObjectWithId({
              kind: IP_PREFIX_POOL,
              data: stringifyWithoutQuotes({
                id: currentObject.id,
                ...newObject,
              }),
            })
          : createObject({
              kind: IP_PREFIX_POOL,
              data: stringifyWithoutQuotes(newObject),
            });

      const mutation = gql`
        ${mutationString}
      `;

      const result = await graphqlClient.mutate({
        mutation,
        context: {
          branch: currentBranch.name,
        },
      });

      const operationType = isUpdate ? "Update" : "Create";
      const successMessage = isUpdate ? "IP prefix pool updated" : "IP prefix pool created";
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={successMessage} />, {
        toastId: `alert-success-ip-prefix-pool-${operationType}`,
      });

      if (onSuccess) {
        const resultData = result?.data?.[`${IP_PREFIX_POOL}${operationType}`];
        await onSuccess(resultData);
      }
    } catch (error: unknown) {
      console.error(
        `An error occurred while ${isUpdate ? "updating" : "creating"} the IP prefix pool:`,
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
}

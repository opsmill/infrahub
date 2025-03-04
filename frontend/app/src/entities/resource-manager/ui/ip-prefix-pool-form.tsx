import { useMemo } from "react";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { NodeFormProps } from "@/shared/components/form/node-form";
import { IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { DynamicSelectFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import { IP_PREFIX_POOL } from "@/entities/resource-manager/constants";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { createObject } from "@/entities/nodes/api/createObject";
import { gql } from "@apollo/client";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/shared/components/ui/alert";
import { NUMBER_POOL_OBJECT } from "@/config/constants";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

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
        const items = genericPrefixSchema.used_by?.map((kind) => {
          const { schema } = getSchema(kind);

          if (!schema)
            return {
              key: kind,
              label: kind,
            };

          return {
            key: kind,
            label: (
              <div className="flex items-center justify-between w-full">
                <span>{schema.label}</span>
                <span className="text-xs text-gray-500">{schema.namespace}</span>
              </div>
            ),
          };
        });

        return {
          ...field,
          type: "select",
          items,
        } as DynamicSelectFieldProps;
      }
      return field;
    });
  }, [props]);

  async function handleSubmit(data: Record<string, FormFieldValue>) {
    try {
      const newObject = getCreateMutationFromFormData(fields, data);

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
    <DynamicForm
      fields={fields}
      onSubmit={(formData: Record<string, FormFieldValue>) =>
        onSubmit ? onSubmit({ formData, fields }) : handleSubmit(formData)
      }
      className="p-4 overflow-auto"
    />
  );
}

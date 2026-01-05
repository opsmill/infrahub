import { gql } from "@apollo/client";
import { useMemo } from "react";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import DynamicForm from "@/shared/components/form/dynamic-form";
import type { NodeFormProps } from "@/shared/components/form/node-form";
import type { DynamicSelectFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { stringifyWithoutQuotes } from "@/shared/utils/string";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { IP_ADDRESS_GENERIC } from "@/entities/ipam/constants";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

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
  const createObject = useCreateObjectMutation();

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
                <div className="flex w-full items-center justify-between">
                  <span>{schema.label}</span>
                  <span className="text-gray-500 text-xs">{schema.namespace}</span>
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
    const newObject = getCreateMutationFromFormData(fields, data, props.objectTemplate?.id);

    if (!Object.keys(newObject).length) {
      return;
    }

    if (currentObject) {
      try {
        const result = await graphqlClient.mutate({
          mutation: gql(
            updateObjectWithId({
              kind: IP_ADDRESS_POOL,
              data: stringifyWithoutQuotes({
                id: currentObject.id,
                ...newObject,
              }),
            })
          ),
          context: { branch: currentBranch.name },
        });

        toast(<Alert type={ALERT_TYPES.SUCCESS} message="IP address pool updated" />, {
          toastId: "alert-success-ip-prefix-pool-update",
        });

        if (onSuccess) {
          const resultData = result?.data?.[`${IP_ADDRESS_POOL}Update`];
          await onSuccess(resultData);
        }
      } catch (error: unknown) {
        console.error("An error occurred while updating the IP address pool:", error);
      }
    } else {
      await createObject.mutateAsync(
        {
          objectKind: IP_ADDRESS_POOL,
          data: newObject,
        },
        {
          onSuccess: async (newNode) => {
            toast(<Alert type={ALERT_TYPES.SUCCESS} message="IP address pool created" />, {
              toastId: "alert-success-ip-prefix-pool-create",
            });

            if (onSuccess) {
              await onSuccess(newNode);
            }
          },
          onError: (error) => {
            console.error("An error occurred while updating the IP address pool:", error);
          },
        }
      );
    }
  }

  return (
    <DynamicForm
      fields={fields}
      onSubmit={(formData: Record<string, FormFieldValue>) =>
        onSubmit ? onSubmit({ formData, fields }) : handleSubmit(formData)
      }
      className="overflow-auto p-4"
    />
  );
};

import { toast } from "react-toastify";

import DynamicForm from "@/shared/components/form/dynamic-form";
import type { NodeFormProps } from "@/shared/components/form/node-form";
import type { DynamicSelectFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { IP_ADDRESS_GENERIC } from "@/entities/ipam/ip-addresses/domain/model/ip-address";
import { IP_PREFIX_GENERIC } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import {
  IP_ADDRESS_POOL,
  IP_PREFIX_POOL,
  type IpPoolKind,
} from "@/entities/resource-manager/domain/model/pool";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface IpPoolKindConfig {
  resourceGenericKind: typeof IP_PREFIX_GENERIC | typeof IP_ADDRESS_GENERIC;
  defaultTypeFieldName: "default_prefix_type" | "default_address_type";
  label: "IP prefix pool" | "IP address pool";
}

const IP_POOL_KIND_CONFIG: Record<IpPoolKind, IpPoolKindConfig> = {
  [IP_PREFIX_POOL]: {
    resourceGenericKind: IP_PREFIX_GENERIC,
    defaultTypeFieldName: "default_prefix_type",
    label: "IP prefix pool",
  },
  [IP_ADDRESS_POOL]: {
    resourceGenericKind: IP_ADDRESS_GENERIC,
    defaultTypeFieldName: "default_address_type",
    label: "IP address pool",
  },
};

interface IpPoolFormProps extends NodeFormProps {
  poolKind: IpPoolKind;
}

export function IpPoolForm({
  poolKind,
  currentObject,
  isUpdate,
  onSuccess,
  onSubmit,
  ...props
}: IpPoolFormProps) {
  const { resourceGenericKind, defaultTypeFieldName, label } = IP_POOL_KIND_CONFIG[poolKind];
  const toastIdPrefix = `alert-success-${label.toLowerCase().replaceAll(" ", "-")}`;
  const { schema: resourceGenericSchema, isGeneric } = useSchema(resourceGenericKind);
  const { currentBranch } = useCurrentBranch();
  const { parentSchema, parentData } = useCurrentFormContext();
  const createObject = useCreateObjectMutation();
  const updateObject = useUpdateObjectMutation();

  const fields = (() => {
    const schemaFields = getFormFieldsFromSchema({
      ...props,
      initialObject: currentObject,
      isDefaultBranch: !!currentBranch.is_default,
      isUpdate,
      parentSchema,
      parentData,
    });

    if (!resourceGenericSchema || !isGeneric) return schemaFields;

    // The attribute is free text, so restrict it to the kinds that inherit from the generic.
    return schemaFields.map((field) => {
      if (field.name === defaultTypeFieldName) {
        const items =
          resourceGenericSchema.used_by?.map((kind) => {
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
                  <span className="text-subtle-muted text-xs">{schema.namespace}</span>
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
  })();

  async function handleSubmit(data: Record<string, FormFieldValue>) {
    const newObject = getCreateMutationFromFormData(fields, data, props.objectTemplate?.id);

    if (!Object.keys(newObject).length) {
      return;
    }

    if (isUpdate && currentObject) {
      await updateObject.mutateAsync(
        {
          objectKind: poolKind,
          data: {
            id: currentObject.id,
            ...newObject,
          },
        },
        {
          onSuccess: async (updatedNode) => {
            toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${label} updated`} />, {
              toastId: `${toastIdPrefix}-update`,
            });
            if (onSuccess) await onSuccess(updatedNode);
          },
          onError: (error) => {
            console.error(`An error occurred while updating the ${label}:`, error);
          },
        }
      );
    } else {
      await createObject.mutateAsync(
        {
          objectKind: poolKind,
          data: newObject,
        },
        {
          onSuccess: async (newNode) => {
            toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${label} created`} />, {
              toastId: `${toastIdPrefix}-create`,
            });
            if (onSuccess) {
              await onSuccess(newNode);
            }
          },
          onError: (error) => {
            console.error(`An error occurred while creating the ${label}:`, error);
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
    />
  );
}

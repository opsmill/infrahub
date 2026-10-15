import { isDeepEqual } from "remeda";

import type { DynamicFieldProps, FormFieldValue } from "@/shared/components/form/type";
import {
  buildFromPoolPayload,
  buildNumberPoolMutationValue,
} from "@/shared/components/form/utils/mutations/buildFromPoolMutationValue";
import { getAllocatedKind } from "@/shared/components/form/utils/updateFormFieldValue";

import { NUMBER_POOL_KIND } from "@/entities/resource-manager/domain/model/pool";

type GetUpdateMutationFromFormDataParams = {
  fields: Array<DynamicFieldProps>;
  formData: Record<string, FormFieldValue>;
};

const getStagedNumber = (value: FormFieldValue["value"]): number | null => {
  if (value === null || typeof value !== "object" || !("from_pool" in value)) return null;
  return "number" in value.from_pool ? (value.from_pool.number ?? null) : null;
};

export const getUpdateMutationFromFormData = ({
  fields,
  formData,
}: GetUpdateMutationFromFormDataParams) => {
  return fields.reduce((acc, field) => {
    const fieldData = formData[field.name];

    if (!fieldData || (field.defaultValue && isDeepEqual(fieldData, field.defaultValue))) {
      return acc;
    }

    const defaultValue = field.defaultValue;
    const fromPoolField = field.pool?.fromPoolRelationshipName;
    if (
      fieldData.source?.type === "pool" &&
      defaultValue?.source?.type === "pool" &&
      defaultValue.source.id === fieldData.source.id
    ) {
      if (fieldData.source.kind === NUMBER_POOL_KIND && !fromPoolField) {
        if (getStagedNumber(fieldData.value) === getStagedNumber(defaultValue.value)) {
          return acc;
        }
      } else {
        // Allocation is idempotent on the reservation identifier, but none is sent for the kind, so
        // a different allocated kind is a real request and must not be dropped.
        const requestedKind =
          fieldData.value && typeof fieldData.value === "object" && "from_pool" in fieldData.value
            ? fieldData.value.from_pool.allocatedKind
            : undefined;
        if (!requestedKind || requestedKind === getAllocatedKind(defaultValue.value)) {
          return acc;
        }
      }
    }

    switch (fieldData.source?.type) {
      case "pool": {
        if (
          fieldData.value &&
          typeof fieldData.value === "object" &&
          "from_pool" in fieldData.value
        ) {
          if (fromPoolField) {
            const clearField =
              field.type === "relationship"
                ? { [field.name]: null }
                : { [field.name]: { value: null } };
            // `<rel>_from_resource_pool` is typed as a plain RelatedNodeInput: sending `prefixlen` or
            // `address_type` there is rejected by GraphQL, so the overrides ride on the payload below.
            return {
              ...acc,
              ...clearField,
              [fromPoolField]: { id: fieldData.value.from_pool.id },
            };
          }
          if (fieldData.source.kind === NUMBER_POOL_KIND) {
            return {
              ...acc,
              [field.name]: buildNumberPoolMutationValue(fieldData.value.from_pool),
            };
          }
          return {
            ...acc,
            [field.name]: {
              from_pool: buildFromPoolPayload(fieldData.value.from_pool, fieldData.source.kind),
            },
          };
        }
        return { ...acc, [field.name]: fieldData.value };
      }
      case "user": {
        if (fieldData.value === null) {
          if (field.type === "relationship") {
            return {
              ...acc,
              [field.name]: null,
              ...(fromPoolField ? { [fromPoolField]: null } : {}),
            };
          }
          return {
            ...acc,
            [field.name]: { value: null },
            ...(fromPoolField ? { [fromPoolField]: null } : {}),
          };
        }

        if (typeof fieldData.value === "object") {
          if (Array.isArray(fieldData.value)) {
            if (!fieldData.value.length) {
              return {
                ...acc,
                [field.name]: null,
              };
            }

            if (fieldData.value.every((value) => typeof value === "string")) {
              return {
                ...acc,
                [field.name]: { value: fieldData.value },
              };
            }

            if (fieldData.value.every((value) => "id" in value)) {
              return {
                ...acc,
                [field.name]: fieldData.value.map(({ id }) => ({ id })),
              };
            }
          }

          if ("id" in fieldData.value) {
            return {
              ...acc,
              [field.name]: { id: fieldData.value.id },
              ...(fromPoolField ? { [fromPoolField]: null } : {}),
            };
          }
        }
        const detachesFromPool =
          field.type === "Number" && !fromPoolField && defaultValue?.source?.type === "pool";
        return {
          ...acc,
          [field.name]: {
            value: fieldData.value === "" ? null : fieldData.value,
            ...(detachesFromPool ? { from_pool: null } : {}),
          },
          ...(fromPoolField ? { [fromPoolField]: null } : {}),
        };
      }
      case "profile":
      case "schema": {
        return { ...acc, [field.name]: { is_default: true } };
      }
      default:
        return acc;
    }
  }, {});
};

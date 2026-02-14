import { isDeepEqual } from "remeda";

import type {
  AttributeValueFromPool,
  DynamicFieldProps,
  FormFieldValue,
  RelationshipValueFromPool,
} from "@/shared/components/form/type";

type GetUpdateMutationFromFormDataParams = {
  fields: Array<DynamicFieldProps>;
  formData: Record<string, FormFieldValue>;
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

    if (
      fieldData.source?.type === "pool" &&
      (field.defaultValue as AttributeValueFromPool | RelationshipValueFromPool)?.source?.id ===
        fieldData?.source?.id
    ) {
      // If the same pool is selected, then remove from the updates
      return acc;
    }

    const fromPoolField = field.pool?.fromPoolRelationshipName;

    switch (fieldData.source?.type) {
      case "pool": {
        if (
          fromPoolField &&
          fieldData.value &&
          typeof fieldData.value === "object" &&
          "from_pool" in fieldData.value
        ) {
          return {
            ...acc,
            [field.name]: null,
            [fromPoolField]: { id: fieldData.value.from_pool.id },
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
          return { ...acc, [field.name]: { value: null } };
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
        return {
          ...acc,
          [field.name]: { value: fieldData.value === "" ? null : fieldData.value },
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

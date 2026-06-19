import { isDeepEqual } from "remeda";

import type {
  AttributeValueFromPool,
  DynamicFieldProps,
  FormFieldValue,
  RelationshipValueFromPool,
} from "@/shared/components/form/type";
import { buildFromPoolPayload } from "@/shared/components/form/utils/mutations/buildFromPoolMutationValue";

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
      return acc;
    }

    const fromPoolField = field.pool?.fromPoolRelationshipName;

    switch (fieldData.source?.type) {
      case "pool": {
        if (
          fieldData.value &&
          typeof fieldData.value === "object" &&
          "from_pool" in fieldData.value
        ) {
          const fromPool = buildFromPoolPayload(fieldData.value.from_pool);
          if (fromPoolField) {
            const clearField =
              field.type === "relationship"
                ? { [field.name]: null }
                : { [field.name]: { value: null } };
            return { ...acc, ...clearField, [fromPoolField]: fromPool };
          }
          return { ...acc, [field.name]: { from_pool: fromPool } };
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
        return {
          ...acc,
          [field.name]: { value: fieldData.value === "" ? null : fieldData.value },
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

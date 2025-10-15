import type { FormFieldValue } from "@/shared/components/form/type";
import type { Filter } from "@/shared/hooks/useFilters";

export const getFiltersFromFormData = (formData: Record<string, FormFieldValue>): Filter[] => {
  return Object.entries(formData).reduce((acc, [fieldName, fieldData]) => {
    if (
      !fieldData ||
      fieldData.value === null ||
      fieldData.value === undefined ||
      (Array.isArray(fieldData.value) && fieldData.value.length === 0)
    ) {
      return acc;
    }

    const fieldValue = fieldData.value;

    if (
      typeof fieldValue === "string" ||
      typeof fieldValue === "number" ||
      typeof fieldValue === "boolean"
    ) {
      return [
        ...acc,
        {
          name: `${fieldName}__value`,
          value: fieldValue,
        },
      ];
    }

    if ("id" in fieldValue) {
      return [
        ...acc,
        {
          name: `${fieldName}__ids`,
          value: [fieldValue],
        },
      ];
    }

    if (Array.isArray(fieldValue)) {
      if (fieldValue.every((value) => typeof value === "string")) {
        return [
          ...acc,
          {
            name: `${fieldName}__values`,
            value: fieldValue,
          },
        ];
      }

      return [
        ...acc,
        {
          name: `${fieldName}__ids`,
          value: fieldValue,
        },
      ];
    }

    return acc;
  }, [] as Filter[]);
};

import { FormFieldValue } from "@/components/form/type";
import { Filter } from "@/hooks/useFilters";

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
          value: [fieldValue.id],
        },
      ];
    }

    if (Array.isArray(fieldValue)) {
      return [
        ...acc,
        {
          name: `${fieldName}__ids`,
          value: fieldValue.map(({ id }) => id),
        },
      ];
    }

    return acc;
  }, [] as Filter[]);
};

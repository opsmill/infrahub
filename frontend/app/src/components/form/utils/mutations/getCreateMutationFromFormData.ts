import {
  DynamicFieldProps,
  FormFieldValue,
  isFormFieldValueFromPool,
} from "@/components/form/type";
import { AttributeType } from "@/utils/getObjectItemDisplayValue";

export const getCreateMutationFromFormData = (
  fields: Array<DynamicFieldProps>,
  formData: Record<string, FormFieldValue>
) => {
  return fields.reduce((acc, field) => {
    const fieldData = formData[field.name];

    if (!fieldData) {
      return acc;
    }

    if (isFormFieldValueFromPool(fieldData)) {
      return { ...acc, [field.name]: fieldData.value };
    }

    if (fieldData.source?.type === "user") {
      if (fieldData.value === null) {
        return { ...acc, [field.name]: { value: null } };
      }

      if (typeof fieldData.value === "object") {
        const fieldValue = Array.isArray(fieldData.value)
          ? fieldData.value.map(({ id }) => ({ id }))
          : { id: fieldData.value.id };
        return {
          ...acc,
          [field.name]: fieldValue,
        };
      }

      const fieldValue = fieldData.value === "" ? null : fieldData.value;
      return {
        ...acc,
        [field.name]: { value: fieldValue },
      };
    }

    return acc;
  }, {});
};

export const getCreateMutationFromFormDataOnly = (
  formData: Record<string, FormFieldValue>,
  currentObject?: Record<string, AttributeType>
) => {
  return Object.entries(formData).reduce((acc, [name, data]) => {
    if (!data) {
      return acc;
    }

    // Avoid updating same values from current object
    if (currentObject && data.value === currentObject[name]?.value) return acc;

    if (data.source?.type === "user") {
      const fieldValue = data.value === "" ? null : data.value;

      return {
        ...acc,
        [name]: Array.isArray(fieldValue) ? fieldValue : { value: fieldValue },
      };
    }

    if (isFormFieldValueFromPool(data)) {
      return { ...acc, [name]: data.value };
    }

    return acc;
  }, {});
};

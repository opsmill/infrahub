import {
  DynamicFieldProps,
  FormFieldValue,
  isFormFieldValueFromPool,
} from "@/components/form/type";

export const getCreateMutationFromFormData = (
  fields: Array<DynamicFieldProps>,
  formData: Record<string, FormFieldValue>
) => {
  return fields.reduce((acc, field) => {
    const fieldData = formData[field.name];

    if (!fieldData) {
      return acc;
    }

    if (fieldData.source?.type === "user") {
      const fieldValue = fieldData.value === "" ? null : fieldData.value;
      return {
        ...acc,
        [field.name]: field.type === "relationship" ? fieldValue : { value: fieldValue },
      };
    }

    if (isFormFieldValueFromPool(fieldData)) {
      return { ...acc, [field.name]: fieldData.value };
    }

    return acc;
  }, {});
};

export const getCreateMutationFromFormDataOnly = (formData: Record<string, FormFieldValue>) => {
  return Object.entries(formData).reduce((acc, [name, data]) => {
    if (!data) {
      return acc;
    }

    if (data.source?.type === "user") {
      const fieldValue = data.value === "" ? null : data.value;
      return {
        ...acc,
        [name]: { value: fieldValue },
      };
    }

    if (isFormFieldValueFromPool(data)) {
      return { ...acc, [name]: data.value };
    }

    return acc;
  }, {});
};

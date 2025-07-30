import { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";
import {
  DynamicFieldProps,
  FormFieldValue,
  isFormFieldValueFromPool,
  isFormFieldValueFromTemplate,
} from "@/shared/components/form/type";

export const getCreateMutationFromFormData = (
  fields: Array<DynamicFieldProps>,
  formData: Record<string, FormFieldValue>,
  objectTemplateId?: string
) => {
  const initialMutation = objectTemplateId ? { object_template: { id: objectTemplateId } } : {};

  return fields.reduce((acc, field) => {
    const fieldData = formData[field.name];

    if (!fieldData || isFormFieldValueFromTemplate(fieldData)) {
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
        if (Array.isArray(fieldData.value)) {
          // To differentiate between list (string[]) and relationship (Node[])
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
          };
        }
      }
      const fieldValue = fieldData.value === "" ? null : fieldData.value;
      return {
        ...acc,
        [field.name]: { value: fieldValue },
      };
    }

    return acc;
  }, initialMutation);
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
      if (typeof data.value === "object" && data.value !== null) {
        if (Array.isArray(data.value)) {
          // To differentiate between list (string[]) and relationship (Node[])
          if (data.value.every((value) => typeof value === "string")) {
            return {
              ...acc,
              [name]: { value: data.value },
            };
          }

          if (data.value.every((value) => "id" in value)) {
            return {
              ...acc,
              [name]: data.value.map(({ id }) => ({ id })),
            };
          }
        }

        if ("id" in data.value) {
          return {
            ...acc,
            [name]: { id: data.value.id },
          };
        }
      }

      const fieldValue = data.value === "" ? null : data.value;

      return {
        ...acc,
        [name]: Array.isArray(fieldValue)
          ? // Uses array of ids for relationships
            fieldValue.map((value) => ({ id: value.id }))
          : { value: fieldValue },
      };
    }

    if (isFormFieldValueFromPool(data)) {
      return { ...acc, [name]: data.value };
    }

    return acc;
  }, {});
};

import {
  type DynamicFieldProps,
  type FormFieldValue,
  isFormFieldValueFromPool,
  isFormFieldValueFromTemplate,
} from "@/shared/components/form/type";

import type { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";

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
      const fromPoolField = field.pool?.fromPoolRelationshipName;
      if (fromPoolField && "from_pool" in fieldData.value) {
        return { ...acc, [fromPoolField]: { id: fieldData.value.from_pool.id } };
      }
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
  currentObject?: Record<string, AttributeType>,
  objectTemplateId?: string
) => {
  const initialMutation = objectTemplateId ? { object_template: { id: objectTemplateId } } : {};

  return Object.entries(formData).reduce((acc, [fieldName, fieldData]) => {
    if (!fieldData || isFormFieldValueFromTemplate(fieldData)) {
      return acc;
    }

    if (currentObject && fieldData.value === currentObject[fieldName]?.value) {
      return acc;
    }

    if (
      currentObject &&
      Array.isArray(fieldData.value) &&
      Array.isArray(currentObject[fieldName]?.value?.edges) &&
      fieldData.value?.length === 0 &&
      currentObject[fieldName]?.value?.edges?.length === 0
    ) {
      return acc;
    }

    if (isFormFieldValueFromPool(fieldData)) {
      return { ...acc, [fieldName]: fieldData.value };
    }

    if (fieldData.source?.type === "user") {
      if (fieldData.value === null) {
        return { ...acc, [fieldName]: null };
      }

      if (typeof fieldData.value === "object") {
        if (Array.isArray(fieldData.value)) {
          // To differentiate between list (string[]) and relationship (Node[])
          if (fieldData.value.every((value) => typeof value === "string")) {
            return {
              ...acc,
              [fieldName]: { value: fieldData.value },
            };
          }

          if (fieldData.value.every((value) => "id" in value)) {
            return {
              ...acc,
              [fieldName]: fieldData.value.map(({ id }) => ({ id })),
            };
          }
        }

        if ("id" in fieldData.value) {
          return {
            ...acc,
            [fieldName]: { id: fieldData.value.id },
          };
        }
      }
      const fieldValue = fieldData.value === "" ? null : fieldData.value;
      return {
        ...acc,
        [fieldName]: { value: fieldValue },
      };
    }

    return acc;
  }, initialMutation);
};

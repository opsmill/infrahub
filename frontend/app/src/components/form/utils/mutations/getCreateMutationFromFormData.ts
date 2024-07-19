import {
  DynamicFieldProps,
  FormAttributeValue,
  FormRelationshipValue,
} from "@/components/form/type";

export const getCreateMutationFromFormData = (
  fields: Array<DynamicFieldProps>,
  formData: Record<string, FormAttributeValue | FormRelationshipValue>
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

    return acc;
  }, {});
};

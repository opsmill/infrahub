import { DynamicFieldProps, FormFieldValue } from "@/components/form/type";
import { isDeepEqual } from "remeda";

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
      field.defaultValue?.source?.id === fieldData?.source?.id
    ) {
      // If the same pool is selected, then remove from the updates
      return acc;
    }

    switch (fieldData.source?.type) {
      case "pool": {
        return { ...acc, [field.name]: fieldData.value };
      }
      case "user": {
        if (fieldData.value === null) {
          if (field.type === "relationship") {
            return { ...acc, [field.name]: null };
          }
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

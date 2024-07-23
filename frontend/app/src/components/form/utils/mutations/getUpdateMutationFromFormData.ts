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

    switch (fieldData.source?.type) {
      case "user": {
        const fieldValue = fieldData.value === "" ? null : fieldData.value;
        return {
          ...acc,
          [field.name]: field.type === "relationship" ? fieldValue : { value: fieldValue },
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

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
      field.defaultValue?.source?.id &&
      fieldData?.source?.id &&
      field.defaultValue?.source?.id === fieldData?.source?.id
    ) {
      // If the same pool is selected, then remove from the updates
      return acc;
    }

    switch (fieldData.source?.type) {
      case "pool":
      case "user": {
        const fieldValue = fieldData.value === "" ? null : fieldData.value;
        console.log("fieldValue: ", fieldValue);
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

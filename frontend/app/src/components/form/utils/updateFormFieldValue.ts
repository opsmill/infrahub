import { FormFieldValue } from "@/components/form/type";
import { isDeepEqual } from "remeda";

export const updateFormFieldValue = (
  newValue: FormFieldValue["value"],
  defaultValue?: FormFieldValue
) => {
  if (defaultValue && isDeepEqual(newValue, defaultValue.value)) return defaultValue;

  return {
    source: { type: "user" },
    value: newValue,
  };
};

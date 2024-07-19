import { FormAttributeValue } from "@/components/form/type";

export const updateFormFieldValue = (
  newValue: FormAttributeValue["value"],
  defaultValue?: FormAttributeValue
): FormAttributeValue => {
  if (defaultValue && newValue === defaultValue.value) return defaultValue;

  return {
    source: { type: "user" },
    value: newValue,
  };
};

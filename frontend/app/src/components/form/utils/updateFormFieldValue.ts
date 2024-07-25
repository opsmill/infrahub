import {
  FormFieldValue,
  FormRelationshipValue,
  RelationshipValueFormPool,
} from "@/components/form/type";
import { isDeepEqual } from "remeda";

export const updateFormFieldValue = (
  newValue: Exclude<FormFieldValue, RelationshipValueFormPool>["value"],
  defaultValue?: FormFieldValue
): FormFieldValue => {
  if (defaultValue && isDeepEqual(newValue, defaultValue.value as typeof newValue)) {
    return defaultValue;
  }

  return {
    source: { type: "user" },
    value: newValue,
  };
};

export const updateRelationshipFieldValue = (
  newValue:
    | { id: string }
    | { id: string }[]
    | { from_pool: { id: string; kind: string; name: string } },
  defaultValue?: FormRelationshipValue
): FormRelationshipValue => {
  if ("from_pool" in newValue) {
    return {
      source: {
        type: "pool",
        id: newValue.from_pool.id,
        kind: newValue.from_pool.kind,
        label: newValue.from_pool.name,
      },
      value: {
        from_pool: {
          id: newValue.from_pool.id,
        },
      },
    };
  }

  return updateFormFieldValue(newValue, defaultValue) as FormRelationshipValue;
};

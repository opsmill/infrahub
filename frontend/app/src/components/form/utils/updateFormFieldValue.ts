import {
  AttributeValueFormPool,
  FormAttributeValue,
  FormFieldValue,
  FormRelationshipValue,
  RelationshipValueFormPool,
} from "@/components/form/type";
import { isDeepEqual } from "remeda";
import { PoolValue } from "@/components/form/pool-selector";

export const updateFormFieldValue = (
  newValue: Exclude<FormFieldValue, AttributeValueFormPool | RelationshipValueFormPool>["value"],
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

export const updateAttributeFieldValue = (
  newValue: { id: string } | { id: string }[] | PoolValue | null,
  defaultValue?: FormAttributeValue
): FormAttributeValue => {
  if (newValue && "from_pool" in newValue) {
    return {
      source: {
        type: "pool",
        id: newValue.from_pool.id,
        kind: newValue.from_pool.kind,
        label: newValue.from_pool.name,
      },
      value: {
        from_pool: newValue.from_pool.id,
      },
    };
  }

  return updateFormFieldValue(newValue, defaultValue) as FormAttributeValue;
};

export const updateRelationshipFieldValue = (
  newValue: { id: string } | { id: string }[] | PoolValue | null,
  defaultValue?: FormRelationshipValue
): FormRelationshipValue => {
  if (newValue && "from_pool" in newValue) {
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

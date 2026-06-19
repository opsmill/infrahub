import { isDeepEqual } from "remeda";

import type { PoolValue } from "@/shared/components/form/pool-selector";
import type {
  AttributeValueFromPool,
  FormAttributeValue,
  FormFieldValue,
  FormRelationshipValue,
  RelationshipValueFromPool,
} from "@/shared/components/form/type";

export const updateFormFieldValue = (
  newValue: Exclude<FormFieldValue, AttributeValueFromPool | RelationshipValueFromPool>["value"],
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
    if (defaultValue?.source?.type === "pool" && defaultValue.source.id === newValue.from_pool.id) {
      // Re-selecting the field's original pool restores the existing allocation
      // unchanged. Allocation is idempotent on the reservation identifier, so the
      // original pool cannot be re-allocated with a different mask — show the
      // resolved value rather than a pending allocation with an editable length.
      return defaultValue;
    }
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
          ...(newValue.from_pool.prefixlen !== undefined && {
            prefixlen: newValue.from_pool.prefixlen,
          }),
        },
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
    if (defaultValue?.source?.type === "pool" && defaultValue.source.id === newValue.from_pool.id) {
      // Re-selecting the field's original pool restores the existing allocation
      // unchanged. Allocation is idempotent on the reservation identifier, so the
      // original pool cannot be re-allocated with a different mask — show the
      // resolved value rather than a pending allocation with an editable length.
      return defaultValue;
    }
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
          ...(newValue.from_pool.prefixlen !== undefined && {
            prefixlen: newValue.from_pool.prefixlen,
          }),
        },
      },
    };
  }

  return updateFormFieldValue(newValue, defaultValue) as FormRelationshipValue;
};

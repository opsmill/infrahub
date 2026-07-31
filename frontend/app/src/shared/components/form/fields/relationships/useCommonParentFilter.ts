import { useEffect, useRef } from "react";
import { useFormContext, useWatch } from "react-hook-form";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import type { FormRelationshipValue } from "@/shared/components/form/type";

import type { NodeFieldsWithMetadata } from "@/entities/nodes/types";
import type { RelationshipSchema } from "@/entities/schema/types";

// Matches no field, so the useWatch call stays unconditional without subscribing to the whole
// form when the relationship declares no common_parent.
const NO_COMMON_PARENT = "__no_common_parent__";

export interface CommonParentFilter {
  isActive: boolean;
  // Filter for the record-shape consumers (many / hierarchical).
  filterQuery?: Record<string, string[]>;
  // Filter for RelationshipInput's `parent` prop (cardinality one).
  parent?: { name: string; value?: string };
  // Seed pre-filling the inline "Add new" form's parent so a created peer stays valid.
  addNewInitialObject?: NodeFieldsWithMetadata;
}

/**
 * For a relationship declaring `common_parent: <X>`, filter the peer options to those sharing the
 * `<X>` parent picked for the sibling `<X>` field, via a single-hop `<X>__ids` filter.
 */
export const useCommonParentFilter = (
  relationship: RelationshipSchema,
  name: string
): CommonParentFilter => {
  const commonParent = relationship.common_parent ?? undefined;
  const watched = useWatch({ name: commonParent ?? NO_COMMON_PARENT }) as
    | FormRelationshipValue
    | undefined;
  const form = useFormContext();

  const value = watched?.value;
  const parentNode = value && !Array.isArray(value) && "id" in value ? value : undefined;
  const chosenParentId = parentNode?.id;

  // A peer picked under one parent no longer satisfies the constraint once the parent changes, so
  // clear it — but skip the first observed value so a pre-filled (edit) selection survives mount.
  const previousParentId = useRef(chosenParentId);
  const isFirstRun = useRef(true);
  useEffect(() => {
    if (!commonParent) return;
    if (isFirstRun.current) {
      isFirstRun.current = false;
      previousParentId.current = chosenParentId;
      return;
    }
    if (previousParentId.current !== chosenParentId) {
      previousParentId.current = chosenParentId;
      form.setValue(name, DEFAULT_FORM_FIELD_VALUE, { shouldDirty: true });
    }
  }, [chosenParentId, commonParent, name, form]);

  if (!commonParent) return { isActive: false };

  return {
    isActive: true,
    filterQuery: chosenParentId ? { [`${commonParent}__ids`]: [chosenParentId] } : undefined,
    parent: { name: commonParent, value: chosenParentId },
    addNewInitialObject: parentNode
      ? ({ [commonParent]: { node: parentNode } } as NodeFieldsWithMetadata)
      : undefined,
  };
};

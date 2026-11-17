import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { ResetAction } from "@/shared/components/form/fields/common";
import { PoolBackedField } from "@/shared/components/form/pool-backed-field";
import type {
  DynamicRelationshipFieldProps,
  FormRelationshipValue,
  PoolValue,
} from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import { updateRelationshipFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/model/relationships";
import {
  RelationshipHierarchicalInput,
  RelationshipHierarchicalManyInput,
} from "@/entities/nodes/relationships/ui/relationship-hierarchical-input";

import { useCommonParentFilter } from "./useCommonParentFilter";

// A nullish label stays `""` so the label falls back to hfid/id.
const toRelationshipNode = (node: NodeCore): RelationshipNode => ({
  ...node,
  display_label: node.display_label ?? "",
});

/**
 * Narrows the stored value to the node the picker renders: a from-pool marker and an array are
 * not one.
 */
const toPickedNode = (value: FormRelationshipValue["value"]): RelationshipNode | null => {
  if (!value || Array.isArray(value) || "from_pool" in value) return null;
  return toRelationshipNode(value);
};

const toPickedNodes = (value: FormRelationshipValue["value"]): RelationshipNode[] | null =>
  Array.isArray(value) ? value.map(toRelationshipNode) : null;

export interface RelationshipHierarchicalFieldProps
  extends Omit<DynamicRelationshipFieldProps, "type"> {}

export default function RelationshipHierarchicalField({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  isBulkUpdate,
  relationship,
  description,
  label,
  name,
  rules,
  unique,
  shouldUnregister,
  disabled,
  pool,
}: RelationshipHierarchicalFieldProps) {
  const commonParent = useCommonParentFilter(relationship, name);

  // Only a cardinality-one relationship can be satisfied from a pool, so the many case never
  // grows a tab strip.
  const poolForCardinality = relationship.cardinality === "one" ? pool : undefined;

  return (
    <FormField
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      shouldUnregister={shouldUnregister}
      render={({ field }) => {
        const fieldData: FormRelationshipValue = field.value ?? DEFAULT_FORM_FIELD_VALUE;

        const { peer } = relationship;

        const onChange = (newValue: NodeCore | NodeCore[] | PoolValue | null) => {
          field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
        };

        return (
          <PoolBackedField
            name={name}
            label={label}
            description={description}
            unique={unique}
            required={!!rules?.required}
            fieldData={fieldData}
            defaultValue={defaultValue}
            // A concrete peer pins the kind the pool allocates, so there is nothing to override.
            pool={poolForCardinality}
            valueTabLabel="Object"
            disabled={disabled}
            onPoolChange={onChange}
          >
            <FormInput>
              {relationship.cardinality === "many" ? (
                <RelationshipHierarchicalManyInput
                  {...field}
                  peer={peer}
                  value={toPickedNodes(fieldData.value)}
                  onChange={onChange}
                  filterQuery={commonParent.filterQuery}
                  hideExplore={commonParent.isActive}
                  addNewInitialObject={commonParent.addNewInitialObject}
                  enforceFilterQueryOnIdSearch={commonParent.isActive}
                />
              ) : (
                <RelationshipHierarchicalInput
                  {...field}
                  peer={peer}
                  value={toPickedNode(fieldData.value)}
                  disabled={disabled}
                  onChange={onChange}
                  filterQuery={commonParent.filterQuery}
                  hideExplore={commonParent.isActive}
                  addNewInitialObject={commonParent.addNewInitialObject}
                  enforceFilterQueryOnIdSearch={commonParent.isActive}
                />
              )}
            </FormInput>

            {canDisplayResetActions(relationship, isBulkUpdate) && (
              <ResetAction field={field} defaultValue={defaultValue} />
            )}

            <FormMessage />
          </PoolBackedField>
        );
      }}
    />
  );
}

import { useState } from "react";
import { useFormContext } from "react-hook-form";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import {
  FieldTabs,
  FieldTabsContent,
  FieldTabsList,
  FieldTabsTrigger,
} from "@/shared/components/form/field-tabs";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import { PoolAllocationPanel } from "@/shared/components/form/pool-allocation-panel";
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

const OBJECT_TAB = "object";
const POOL_TAB = "from-pool";
type FieldTab = typeof OBJECT_TAB | typeof POOL_TAB;

// `NodeCore.display_label` is optional, `RelationshipNode.display_label` is not; keeping a
// nullish label as `""` leaves `getNodeLabel` on its hfid/id fallback, exactly as before.
const toRelationshipNode = (node: NodeCore): RelationshipNode => ({
  ...node,
  display_label: node.display_label ?? "",
});

/**
 * The peer the single picker renders. A from-pool marker is not a node: the pool tab names the
 * pool itself, so the picker shows nothing rather than a stand-in node labelled "Allocated by
 * pool", which the tabs made redundant. An array belongs to the cardinality-many picker.
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
  const form = useFormContext();

  const [activeTab, setActiveTab] = useState<FieldTab>(OBJECT_TAB);

  // Switching tabs abandons whatever was staged under the old one, so the field goes back to
  // the value it had on open — not to empty. That makes merely looking at the other tab a
  // no-op: `getUpdateMutationFromFormData` skips a field that deep-equals its default, so
  // nothing is submitted and an existing value is never silently cleared. It also stops the
  // nested `${name}.value.from_pool.*` fields surviving a switch.
  const handleTabChange = (tab: string) => {
    setActiveTab(tab === POOL_TAB ? POOL_TAB : OBJECT_TAB);
    form.setValue(name, defaultValue ?? DEFAULT_FORM_FIELD_VALUE, { shouldDirty: true });
  };

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
        const selectedPoolId = fieldData?.source?.type === "pool" ? fieldData.source.id : null;

        const onChange = (newValue: NodeCore | NodeCore[] | PoolValue | null) => {
          field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
        };

        const objectPanel = (
          <>
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
          </>
        );

        // Rendered inside the field so it can carry `fieldData`: that is what puts the
        // provenance badge (pool / profile / template) beside the label.
        const fieldLabel = (
          <LabelFormField
            label={label}
            unique={unique}
            required={!!rules?.required}
            description={description}
            fieldData={fieldData}
          />
        );

        if (!poolForCardinality) {
          return (
            <div className="flex flex-col gap-2">
              {fieldLabel}
              {objectPanel}
            </div>
          );
        }

        return (
          <FieldTabs
            value={activeTab}
            onValueChange={handleTabChange}
            // Switching discards the staged value, so it must take a deliberate press rather
            // than merely arrowing across the strip.
            activationMode="manual"
            // The label is a child of the tab root so it can carry `fieldData`; the root adds
            // no spacing of its own, so give it the same rhythm the untabbed fields use or the
            // label sits flush against the strip.
            className="space-y-2"
          >
            {fieldLabel}

            <FieldTabsList>
              <FieldTabsTrigger value={OBJECT_TAB} disabled={disabled}>
                Object
              </FieldTabsTrigger>
              <FieldTabsTrigger value={POOL_TAB} disabled={disabled}>
                From pool
              </FieldTabsTrigger>
            </FieldTabsList>

            <FieldTabsContent value={OBJECT_TAB}>{objectPanel}</FieldTabsContent>

            <FieldTabsContent value={POOL_TAB}>
              <PoolAllocationPanel
                name={name}
                poolKind={poolForCardinality.kind}
                poolDefaultAllocatedObjectKind={poolForCardinality.defaultAllocatedObjectKind}
                // No `allocatableKinds`: a concrete peer pins the kind the pool allocates,
                // so there is nothing to override.
                options={poolForCardinality.options}
                selectedPoolId={selectedPoolId}
                value={fieldData}
                disabled={disabled}
                onChange={onChange}
              />
            </FieldTabsContent>
          </FieldTabs>
        );
      }}
    />
  );
}

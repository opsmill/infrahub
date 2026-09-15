import { useEffect, useState } from "react";
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
import { getParentRelationship } from "@/shared/components/form/utils/getParentRelationship";
import { updateRelationshipFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { RelationshipInput } from "@/shared/components/inputs/relationship-one";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { useDefaultParent } from "@/entities/nodes/relationships/ui/queries/get-default-parent.query";

import { useCommonParentFilter } from "./useCommonParentFilter";

const OBJECT_TAB = "object";
const POOL_TAB = "from-pool";
type FieldTab = typeof OBJECT_TAB | typeof POOL_TAB;

/**
 * The peer the object picker renders. A from-pool marker is not a node — the pool tab shows the
 * pool itself — and an array belongs to the cardinality-many field, so both narrow to nothing
 * here rather than being asserted into a `Node`.
 */
const toPickedNode = (fieldData: FormRelationshipValue | undefined): Node | null => {
  const value = fieldData?.value;
  if (!value || Array.isArray(value) || "from_pool" in value) return null;
  return { ...value, display_label: value.display_label ?? "" };
};

export interface RegularRelationshipFieldProps extends DynamicRelationshipFieldProps {
  parentDisabled?: boolean;
  defaultParent?: Node | null;
}

export const NodeRelationshipField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  isBulkUpdate,
  relationship,
  description,
  label,
  name,
  rules,
  unique,
  type,
  options,
  parent,
  pool,
  shouldUnregister,
  ...props
}: RegularRelationshipFieldProps) => {
  const parentRelationship = getParentRelationship(relationship.peer);
  const commonParent = useCommonParentFilter(relationship, name);
  // When common_parent drives the filter from a sibling field, the manual "Parent" picker
  // is redundant — hide it and source the peer filter from the sibling value instead.
  const showManualParent = !commonParent.isActive && !!parentRelationship;

  const { data: defaultParent } = useDefaultParent({
    defaultValue,
    parentRelationship: parentRelationship
      ? {
          peer: parentRelationship.peer,
          direction: parentRelationship.direction,
          identifier: parentRelationship.identifier ?? undefined,
        }
      : undefined,
  });

  const [selectedParent, setSelectedParent] = useState<Node | null>(defaultParent || null);

  useEffect(() => {
    if (!selectedParent && defaultParent) {
      setSelectedParent(defaultParent);
    }
  }, [defaultParent, selectedParent]);

  const form = useFormContext();

  const [activeTab, setActiveTab] = useState<FieldTab>(OBJECT_TAB);

  // Switching tabs abandons whatever was staged under the old one, so the field goes back
  // to the value it had on open — not to empty. That makes merely looking at the other tab
  // a no-op: `getUpdateMutationFromFormData` skips a field that deep-equals its default, so
  // nothing is submitted and an existing value is never silently cleared.
  const handleTabChange = (tab: string) => {
    setActiveTab(tab === POOL_TAB ? POOL_TAB : OBJECT_TAB);
    setSelectedParent(null);
    form.setValue(name, defaultValue ?? DEFAULT_FORM_FIELD_VALUE, { shouldDirty: true });
  };

  return (
    <div className="space-y-2">
      {showManualParent && (
        <LabelFormField
          label={label}
          unique={unique}
          required={!!rules?.required}
          description={description}
        />
      )}
      {showManualParent && (
        <FormField
          key={`${name}_parent`}
          name={name}
          rules={rules}
          defaultValue={defaultValue}
          shouldUnregister={shouldUnregister}
          render={({ field }) => {
            return (
              <div className="relative flex flex-col">
                <LabelFormField
                  label={parentRelationship?.label ?? "Parent"}
                  description="Parent to filter the available nodes"
                  unique={unique}
                  required={!!rules?.required}
                  variant="small"
                />
                <FormInput>
                  <RelationshipInput
                    {...field}
                    {...props}
                    value={selectedParent}
                    peer={parentRelationship?.peer}
                    placeholder="Select a parent"
                    disabled={props.parentDisabled || props.disabled}
                    onChange={(value: Node | PoolValue | null) =>
                      setSelectedParent(value as Node | null)
                    }
                    className="mt-1"
                  />
                </FormInput>
                <FormMessage />
              </div>
            );
          }}
        />
      )}
      <FormField
        key={name}
        name={name}
        rules={rules}
        defaultValue={defaultValue}
        shouldUnregister={shouldUnregister}
        render={({ field }) => {
          const fieldData: FormRelationshipValue = field.value ?? DEFAULT_FORM_FIELD_VALUE;

          const { peer } = relationship;
          const selectedPoolId = fieldData?.source?.type === "pool" ? fieldData.source.id : null;

          const onChange = (newValue: Node | PoolValue | null) => {
            field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
          };

          const objectPanel = (
            <>
              <FormInput>
                <RelationshipInput
                  {...field}
                  {...props}
                  value={toPickedNode(fieldData)}
                  onChange={onChange}
                  peer={peer}
                  parent={
                    commonParent.isActive
                      ? commonParent.parent
                      : { name: parentRelationship?.name, value: selectedParent?.id }
                  }
                  addNewInitialObject={commonParent.addNewInitialObject}
                />
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
              variant={showManualParent ? "small" : undefined}
              fieldData={fieldData}
            />
          );

          if (!pool) {
            return (
              <div className="relative flex flex-col space-y-2">
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
            >
              {fieldLabel}

              <FieldTabsList>
                <FieldTabsTrigger value={OBJECT_TAB} disabled={props.disabled}>
                  Object
                </FieldTabsTrigger>
                <FieldTabsTrigger value={POOL_TAB} disabled={props.disabled}>
                  From pool
                </FieldTabsTrigger>
              </FieldTabsList>

              <FieldTabsContent value={OBJECT_TAB}>{objectPanel}</FieldTabsContent>

              <FieldTabsContent value={POOL_TAB}>
                <PoolAllocationPanel
                  name={name}
                  poolKind={pool.kind}
                  poolDefaultAllocatedObjectKind={pool.defaultAllocatedObjectKind}
                  // No `allocatableKinds`: a concrete peer pins the kind the pool allocates,
                  // so there is nothing to override.
                  options={pool.options}
                  fromPoolRelationshipName={pool.fromPoolRelationshipName}
                  selectedPoolId={selectedPoolId}
                  value={fieldData}
                  disabled={props.disabled}
                  onChange={onChange}
                />
              </FieldTabsContent>
            </FieldTabs>
          );
        }}
      />
    </div>
  );
};

import { useEffect, useState } from "react";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import { PoolBackedField } from "@/shared/components/form/pool-backed-field";
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

          const onChange = (newValue: Node | PoolValue | null) => {
            field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
          };

          return (
            <PoolBackedField
              name={name}
              label={label}
              description={description}
              unique={unique}
              required={!!rules?.required}
              labelVariant={showManualParent ? "small" : undefined}
              fieldData={fieldData}
              defaultValue={defaultValue}
              // A concrete peer pins the kind the pool allocates, so there is nothing to override.
              pool={pool}
              valueTabLabel="Object"
              disabled={props.disabled}
              untabbedClassName="relative"
              onPoolChange={onChange}
              onTabSwitch={() => setSelectedParent(null)}
            >
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
            </PoolBackedField>
          );
        }}
      />
    </div>
  );
};

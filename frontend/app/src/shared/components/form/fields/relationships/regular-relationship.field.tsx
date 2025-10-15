import { useEffect, useState } from "react";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import type { PoolValue } from "@/shared/components/form/pool-selector";
import type {
  DynamicRelationshipFieldProps,
  FormRelationshipValue,
} from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import { getParentRelationship } from "@/shared/components/form/utils/getParentRelationship";
import { updateRelationshipFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { PoolSelect } from "@/shared/components/inputs/pool-select";
import { RelationshipInput } from "@/shared/components/inputs/relationship-one";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { useDefaultParent } from "@/entities/nodes/relationships/domain/get-default-parent.query";
import { getPoolKindFromSchema } from "@/entities/resource-manager/utils/get-pool-kind-from-schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

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
  schema,
  shouldUnregister,
  ...props
}: RegularRelationshipFieldProps) => {
  const parentRelationship = getParentRelationship(relationship.peer);

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
      {parentRelationship && (
        <LabelFormField
          label={label}
          unique={unique}
          required={!!rules?.required}
          description={description}
        />
      )}
      {parentRelationship && (
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
          const fieldData: FormRelationshipValue = field.value;

          const { peer } = relationship;
          const { schema: peerSchema } = useSchema(peer);
          const poolKind = peerSchema ? getPoolKindFromSchema(peerSchema) : null;
          const selectedPoolId = fieldData?.source?.type === "pool" ? fieldData.source.id : null;

          const onChange = (newValue: Node | PoolValue | null) => {
            field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
          };

          const value =
            fieldData?.value && !Array.isArray(fieldData.value) ? (fieldData.value as Node) : null;

          return (
            <div className="relative flex flex-col space-y-2">
              <LabelFormField
                label={label}
                unique={unique}
                required={!!rules?.required}
                description={description}
                variant={parentRelationship ? "small" : undefined}
                fieldData={fieldData}
              />

              <div className="flex gap-2">
                <FormInput>
                  <RelationshipInput
                    {...field}
                    {...props}
                    value={value}
                    onChange={onChange}
                    peer={peer}
                    parent={{ name: parentRelationship?.name, value: selectedParent?.id }}
                  />
                </FormInput>

                {poolKind && peerSchema && (
                  <PoolSelect
                    poolKind={poolKind}
                    poolDefaultAllocatedObjectKind={peerSchema.kind as string}
                    selectedPoolId={selectedPoolId}
                    onChange={onChange}
                  />
                )}
              </div>

              {canDisplayResetActions(relationship, isBulkUpdate) && (
                <ResetAction field={field} defaultValue={defaultValue} />
              )}

              <FormMessage />
            </div>
          );
        }}
      />
    </div>
  );
};

import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import {
  RelationshipHierarchicalInput,
  RelationshipHierarchicalManyInput,
} from "@/entities/nodes/relationships/ui/relationship-hierarchical-input";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField } from "@/shared/components/form/fields/common";
import { PoolValue } from "@/shared/components/form/pool-selector";
import {
  DynamicRelationshipFieldProps,
  FormRelationshipValue,
  PoolSource,
} from "@/shared/components/form/type";
import { getPoolKindFromSchema } from "@/shared/components/form/utils/get-pool-kind-from-schema";
import { updateRelationshipFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { PoolSelect } from "@/shared/components/inputs/pool-select";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

export interface RelationshipHierarchicalFieldProps
  extends Omit<DynamicRelationshipFieldProps, "type"> {}

export default function RelationshipHierarchicalField({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  description,
  label,
  name,
  rules,
  unique,
  ...props
}: RelationshipHierarchicalFieldProps) {
  return (
    <FormField
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => {
        const fieldData: FormRelationshipValue = field.value;
        const value: RelationshipNode | RelationshipNode[] | null =
          fieldData.value && "from_pool" in fieldData.value
            ? {
                id: fieldData.value.from_pool.id,
                display_label: "Allocated by pool",
                __typename: (fieldData.source as PoolSource).kind,
              }
            : fieldData.value;

        const { peer } = props.relationship;
        const { schema: peerSchema } = useSchema(peer);
        const poolKind = peerSchema ? getPoolKindFromSchema(peerSchema) : null;
        const selectedPoolId = fieldData?.source?.type === "pool" ? fieldData.source.id : null;

        const onChange = (newValue: RelationshipNode | RelationshipNode[] | PoolValue | null) => {
          field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
        };

        return (
          <div className="flex flex-col gap-2">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
              fieldData={fieldData}
            />

            <div className="flex gap-2">
              <FormInput>
                {props.relationship.cardinality === "many" ? (
                  <RelationshipHierarchicalManyInput
                    {...field}
                    peer={peer}
                    value={value as RelationshipNode[] | null}
                    onChange={onChange}
                  />
                ) : (
                  <RelationshipHierarchicalInput
                    {...field}
                    peer={props.relationship.peer}
                    value={value as RelationshipNode | null}
                    onChange={onChange}
                  />
                )}
              </FormInput>

              {props.relationship.cardinality === "one" && poolKind && (
                <PoolSelect
                  poolKind={poolKind}
                  selectedPoolId={selectedPoolId}
                  onChange={onChange}
                />
              )}
            </div>

            <FormMessage />
          </div>
        );
      }}
    />
  );
}

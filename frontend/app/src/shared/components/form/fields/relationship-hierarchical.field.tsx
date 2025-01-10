import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField } from "@/shared/components/form/fields/common";
import { DynamicRelationshipFieldProps, FormRelationshipValue } from "@/shared/components/form/type";
import { updateRelationshipFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { RelationshipNode } from "@/screens/objects/relationships/domain/types";
import {
  RelationshipHierarchicalInput,
  RelationshipHierarchicalManyInput,
} from "@/screens/objects/relationships/ui/relationship-hierarchical-input";

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

        return (
          <div className="flex flex-col gap-2">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
              fieldData={fieldData}
            />

            <FormInput>
              {props.relationship.cardinality === "many" ? (
                <RelationshipHierarchicalManyInput
                  {...field}
                  peer={props.relationship.peer}
                  value={fieldData.value as RelationshipNode[] | null}
                  onChange={(newValue) => {
                    field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
                  }}
                />
              ) : (
                <RelationshipHierarchicalInput
                  {...field}
                  peer={props.relationship.peer}
                  value={fieldData.value as RelationshipNode | null}
                  onChange={(newValue) => {
                    field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
                  }}
                />
              )}
            </FormInput>

            <FormMessage />
          </div>
        );
      }}
    />
  );
}

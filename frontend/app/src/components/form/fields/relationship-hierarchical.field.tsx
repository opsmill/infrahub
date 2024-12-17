import { DEFAULT_FORM_FIELD_VALUE } from "@/components/form/constants";
import { LabelFormField } from "@/components/form/fields/common";
import { DynamicRelationshipFieldProps, FormRelationshipValue } from "@/components/form/type";
import { updateRelationshipFieldValue } from "@/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { RelationshipHierarchicalInput } from "@/screens/objects/relationships/components/relationship-hierarchical-input";
import { RelationshipNode } from "@/screens/objects/relationships/domain/types";

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
              <RelationshipHierarchicalInput
                peer={props.relationship.peer}
                value={fieldData.value as RelationshipNode | null}
                onChange={(newValue) => {
                  field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
                }}
              />
            </FormInput>

            <FormMessage />
          </div>
        );
      }}
    />
  );
}

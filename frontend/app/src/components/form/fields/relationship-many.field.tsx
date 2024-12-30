import { LabelFormField } from "@/components/form/fields/common";
import { DynamicRelationshipFieldProps, FormRelationshipValue } from "@/components/form/type";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";

import { DEFAULT_FORM_FIELD_VALUE } from "@/components/form/constants";
import { updateRelationshipFieldValue } from "@/components/form/utils/updateFormFieldValue";
import { RelationshipManyInput } from "@/components/inputs/relationship-many";
import { classNames } from "@/utils/common";
import { Node } from "@/utils/getObjectItemDisplayValue";

export interface RelationshipManyInputProps extends Omit<DynamicRelationshipFieldProps, "type"> {}

export default function RelationshipManyField({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  description,
  label,
  name,
  rules,
  unique,
  ...props
}: RelationshipManyInputProps) {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field, fieldState }) => {
        const fieldData: FormRelationshipValue = field.value;
        const { error } = fieldState;

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
              <RelationshipManyInput
                {...field}
                {...props}
                className={classNames(
                  error &&
                    "has-[>:last-child:focus]:ring-red-500/25 has-[>:last-child:focus]:border-red-500"
                )}
                peer={props.relationship.peer}
                value={fieldData.value as Node[] | null}
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

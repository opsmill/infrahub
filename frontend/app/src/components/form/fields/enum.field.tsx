import { LabelFormField } from "@/components/form/fields/common";
import { DynamicEnumFieldProps, FormAttributeValue } from "@/components/form/type";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";

import { DEFAULT_FORM_FIELD_VALUE } from "@/components/form/constants";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";
import { Enum, EnumProps } from "@/components/inputs/enum";

export interface EnumFieldProps
  extends Omit<DynamicEnumFieldProps, "type">,
    Omit<EnumProps, "defaultValue" | "value" | "name" | "items"> {}

const EnumField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  description,
  label,
  name,
  rules,
  unique,
  items,
  schema,
  field: attributeSchema,
  ...props
}: EnumFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;

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
              <Enum
                {...field}
                {...props}
                items={items as Array<string | number>}
                fieldSchema={attributeSchema}
                schema={schema}
                value={fieldData?.value as string | number | null}
                onChange={(newValue) => {
                  field.onChange(updateFormFieldValue(newValue, defaultValue));
                }}
              />
            </FormInput>

            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default EnumField;

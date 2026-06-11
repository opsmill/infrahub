import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import type { DynamicEnumFieldProps, FormAttributeValue } from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { Enum, type EnumProps } from "@/shared/components/inputs/enum";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

export interface EnumFieldProps
  extends Omit<DynamicEnumFieldProps, "type">,
    Omit<EnumProps, "defaultValue" | "value" | "name" | "items" | "onChange"> {}

const EnumField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  deprecation,
  isBulkUpdate,
  attribute,
  description,
  label,
  name,
  rules,
  unique,
  items,
  schema,
  shouldUnregister,
  ...props
}: EnumFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      shouldUnregister={shouldUnregister}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;

        return (
          <div className="flex flex-col gap-2">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              deprecation={deprecation}
              description={description}
              fieldData={fieldData}
            />

            <FormInput>
              <Enum
                {...field}
                {...props}
                items={items as Array<string | number>}
                fieldSchema={attribute}
                schema={schema}
                value={fieldData?.value as string | number | null}
                onChange={(newValue) => {
                  field.onChange(updateFormFieldValue(newValue, defaultValue));
                }}
              />
            </FormInput>

            {!props.disabled && canDisplayResetActions(attribute, isBulkUpdate) && (
              <ResetAction field={field} defaultValue={defaultValue} />
            )}

            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default EnumField;

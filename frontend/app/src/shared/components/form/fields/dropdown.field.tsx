import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import type { DynamicDropdownFieldProps, FormAttributeValue } from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { Dropdown, type DropdownProps } from "@/shared/components/inputs/dropdown";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

export interface DropdownFieldProps
  extends Omit<DynamicDropdownFieldProps, "type">,
    Omit<DropdownProps, "defaultValue" | "name" | "options" | "onChange"> {}

const DropdownField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  attribute,
  deprecation,
  isBulkUpdate,
  description,
  items,
  label,
  name,
  rules,
  unique,
  shouldUnregister,
  ...props
}: DropdownFieldProps) => {
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
              <Dropdown
                {...field}
                {...props}
                field={attribute}
                items={items}
                value={fieldData?.value as string | null}
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

export default DropdownField;

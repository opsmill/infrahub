import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { DynamicEnumFieldProps } from "@/components/form/type";
import { ComboboxProps } from "@/components/ui/combobox";
import { LabelFormField } from "@/components/form/fields/common";
import { Select } from "@/components/inputs/select";

export interface EnumFieldProps
  extends Omit<DynamicEnumFieldProps, "type">,
    Omit<ComboboxProps, "defaultValue" | "name" | "items"> {}

const EnumField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  items,
  ...props
}: EnumFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => {
        return (
          <div className="flex flex-col">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
            />

            <FormInput>
              <Select {...field} {...props} options={items} enum className="w-full" />
            </FormInput>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default EnumField;

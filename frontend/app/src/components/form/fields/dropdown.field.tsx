import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { Select, SelectProps } from "@/components/inputs/select";
import { DynamicDropdownFieldProps } from "@/components/form/type";
import { LabelFormField } from "@/components/form/fields/common";

export interface DropdownFieldProps
  extends Omit<DynamicDropdownFieldProps, "type">,
    Omit<SelectProps, "defaultValue" | "name" | "options"> {}

const DropdownField = ({
  defaultValue,
  description,
  items,
  label,
  name,
  rules,
  unique,
  ...props
}: DropdownFieldProps) => {
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
              <Select {...field} {...props} options={items} dropdown className="w-full" />
            </FormInput>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default DropdownField;

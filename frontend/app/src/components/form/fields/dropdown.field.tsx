import { FormField, FormInput, FormLabel, FormMessage } from "@/components/ui/form";
import { Select, SelectProps } from "@/components/inputs/select";
import { DynamicDropdownFieldProps } from "@/components/form/type";
import { QuestionMark } from "@/components/display/question-mark";

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
            <div className="px-1 mb-1 flex justify-between items-center gap-1">
              <FormLabel>
                {label} {rules?.required && "*"}
              </FormLabel>

              {description && <QuestionMark message={description} />}
            </div>

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

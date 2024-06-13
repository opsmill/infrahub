import { FormField, FormInput, FormLabel, FormMessage } from "@/components/ui/form";
import { DynamicEnumFieldProps } from "@/components/form/type";
import { Combobox, ComboboxProps } from "@/components/ui/combobox";
import { QuestionMark } from "@/components/display/question-mark";

export interface EnumFieldProps
  extends Omit<DynamicEnumFieldProps, "type">,
    Omit<ComboboxProps, "defaultValue" | "name" | "items"> {}

const EnumField = ({ defaultValue, description, label, name, rules, ...props }: EnumFieldProps) => {
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
              <Combobox {...field} {...props} />
            </FormInput>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default EnumField;

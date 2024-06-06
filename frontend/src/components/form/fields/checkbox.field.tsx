import { FormField, FormInput, FormLabel, FormMessage } from "../../ui/form";
import { FormFieldProps } from "./common";
import { Checkbox } from "../../inputs/checkbox";

const CheckboxField = ({ defaultValue, label, name, rules }: FormFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => (
        <div className="flex flex-col items-start">
          <div className="flex items-center">
            <FormInput>
              <Checkbox {...field} />
            </FormInput>

            <FormLabel className="ml-1">
              {label} {rules?.required && "*"}
            </FormLabel>
          </div>
          <FormMessage />
        </div>
      )}
    />
  );
};

export default CheckboxField;

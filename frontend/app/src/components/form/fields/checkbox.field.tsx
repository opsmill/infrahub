import { Checkbox } from "@/components/inputs/checkbox";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { FormFieldProps } from "@/components/form/type";
import { LabelFormField } from "@/components/form/fields/common";

export interface CheckboxFieldProps extends FormFieldProps {}

const CheckboxField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  ...props
}: CheckboxFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={{
        validate: {
          ...rules?.validate,
          required: (checked: boolean) => {
            if (rules?.required) return checked !== undefined && checked !== null;

            return true;
          },
        },
      }}
      defaultValue={defaultValue}
      render={({ field }) => {
        const { value, ...fieldMethodsWithoutValue } = field;

        return (
          <div className="relative flex flex-col">
            <div className="flex items-center">
              <FormInput>
                <Checkbox {...fieldMethodsWithoutValue} {...props} checked={!!value} />
              </FormInput>

              <LabelFormField
                className="m-0"
                label={label}
                unique={unique}
                required={!!rules?.required}
                description={description}
              />
            </div>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default CheckboxField;

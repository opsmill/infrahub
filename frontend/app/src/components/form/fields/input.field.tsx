import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { Input, InputProps } from "@/components/ui/input";
import { FormFieldProps } from "@/components/form/type";
import { LabelFormField } from "@/components/form/fields/common";

export interface InputFieldProps
  extends FormFieldProps,
    Omit<InputProps, "defaultValue" | "name"> {}

const InputField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  ...props
}: InputFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => {
        // Not passing "value" is needed to prevent error on uncontrolled component
        // eslint-disable-next-line @typescript-eslint/no-unused-vars,no-unused-vars
        const { value, onChange, ...fieldMethodsWithoutValue } = field;
        return (
          <div className="flex flex-col">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
            />

            <FormInput>
              <Input
                {...fieldMethodsWithoutValue}
                {...props}
                onChange={(event) => {
                  onChange(
                    props.type === "number" ? event.target.valueAsNumber : event.target.value
                  );
                }}
                value={value ?? ""}
              />
            </FormInput>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default InputField;

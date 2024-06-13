import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { FormFieldProps } from "@/components/form/type";
import List from "@/components/list";
import { LabelFormField } from "@/components/form/fields/common";

const ListField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  ...props
}: FormFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => (
        <div className="flex flex-col">
          <LabelFormField
            label={label}
            unique={unique}
            required={!!rules?.required}
            description={description}
          />

          <FormInput>
            <List isProtected={props.disabled} {...field} {...props} />
          </FormInput>
          <FormMessage />
        </div>
      )}
    />
  );
};

export default ListField;

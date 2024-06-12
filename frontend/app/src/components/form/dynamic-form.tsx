import { Button } from "@/components/buttons/button-primitive";
import { Form, FormProps, FormSubmit } from "@/components/ui/form";
import { DynamicFieldProps } from "@/components/form/type";
import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import CheckboxField from "./fields/checkbox.field";
import InputField from "./fields/input.field";
import PasswordInputField from "./fields/password-input.field";
import TextareaField from "./fields/textarea.field";

interface DynamicFormProps extends FormProps {
  fields: Array<DynamicFieldProps>;
  onCancel?: () => void;
  submitLabel?: string;
}

const DynamicForm = ({ fields, onCancel, submitLabel, ...props }: DynamicFormProps) => {
  return (
    <Form {...props}>
      {fields.map((field) => (
        <DynamicInput key={field.name} {...field} />
      ))}

      <div className="text-right">
        {onCancel && (
          <Button variant="outline" className="mr-2" onClick={onCancel}>
            Cancel
          </Button>
        )}

        <FormSubmit>{submitLabel ?? "Save"}</FormSubmit>
      </div>
    </Form>
  );
};

const DynamicInput = ({ type, ...props }: DynamicFieldProps) => {
  switch (type) {
    case SCHEMA_ATTRIBUTE_KIND.CHECKBOX:
      return <CheckboxField {...props} />;
    case SCHEMA_ATTRIBUTE_KIND.PASSWORD:
      return <PasswordInputField {...props} />;
    case SCHEMA_ATTRIBUTE_KIND.TEXT:
      return <InputField {...props} />;
    case SCHEMA_ATTRIBUTE_KIND.TEXTAREA:
      return <TextareaField {...props} />;
    default:
      return <div>WIP: no component yet</div>;
  }
};

export default DynamicForm;

import { Button } from "@/components/buttons/button-primitive";
import { Form, FormProps, FormSubmit } from "@/components/ui/form";
import { DynamicFieldProps } from "@/components/form/type";
import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import ColorField from "@/components/form/fields/color.field";
import CheckboxField from "@/components/form/fields/checkbox.field";
import DatetimeField from "@/components/form/fields/datetime.field";
import DropdownField from "@/components/form/fields/dropdown.field";
import InputField from "@/components/form/fields/input.field";
import JsonField from "@/components/form/fields/json.field";
import ListField from "@/components/form/fields/list.field";
import PasswordInputField from "@/components/form/fields/password-input.field";
import TextareaField from "@/components/form/fields/textarea.field";
import RelationshipField from "@/components/form/fields/relationship.field";
import { warnUnexpectedType } from "@/utils/common";
import EnumField from "@/components/form/fields/enum.field";

export interface DynamicFormProps extends FormProps {
  fields: Array<DynamicFieldProps>;
  onCancel?: () => void;
  submitLabel?: string;
}

const DynamicForm = ({ fields, onCancel, submitLabel, ...props }: DynamicFormProps) => {
  const formDefaultValues = fields.reduce(
    (acc, field) => ({ ...acc, [field.name]: field.defaultValue }),
    {}
  );

  return (
    <Form {...props} defaultValues={formDefaultValues}>
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

const DynamicInput = (props: DynamicFieldProps) => {
  const { type, ...otherProps } = props;
  switch (type) {
    case SCHEMA_ATTRIBUTE_KIND.DATETIME:
      return <DatetimeField {...otherProps} />;
    case SCHEMA_ATTRIBUTE_KIND.COLOR:
      return <ColorField {...otherProps} />;
    case SCHEMA_ATTRIBUTE_KIND.BOOLEAN:
    case SCHEMA_ATTRIBUTE_KIND.CHECKBOX:
      return <CheckboxField {...otherProps} />;
    case SCHEMA_ATTRIBUTE_KIND.DROPDOWN:
      return <DropdownField {...(otherProps as Omit<typeof props, "type">)} />;
    case SCHEMA_ATTRIBUTE_KIND.JSON:
      return <JsonField {...otherProps} />;
    case SCHEMA_ATTRIBUTE_KIND.LIST:
      return <ListField {...otherProps} />;
    case SCHEMA_ATTRIBUTE_KIND.BANDWIDTH:
    case SCHEMA_ATTRIBUTE_KIND.NUMBER:
      return <InputField {...otherProps} type="number" />;
    case SCHEMA_ATTRIBUTE_KIND.PASSWORD:
    case SCHEMA_ATTRIBUTE_KIND.HASHED_PASSWORD:
      return <PasswordInputField {...otherProps} />;
    case SCHEMA_ATTRIBUTE_KIND.ANY:
    case SCHEMA_ATTRIBUTE_KIND.EMAIL:
    case SCHEMA_ATTRIBUTE_KIND.FILE:
    case SCHEMA_ATTRIBUTE_KIND.ID:
    case SCHEMA_ATTRIBUTE_KIND.IP_HOST:
    case SCHEMA_ATTRIBUTE_KIND.IP_NETWORK:
    case SCHEMA_ATTRIBUTE_KIND.MAC_ADDRESS:
    case SCHEMA_ATTRIBUTE_KIND.TEXT:
    case SCHEMA_ATTRIBUTE_KIND.URL:
      return <InputField {...otherProps} />;
    case SCHEMA_ATTRIBUTE_KIND.TEXTAREA:
      return <TextareaField {...otherProps} />;
    case "enum":
      return <EnumField {...(otherProps as Omit<typeof props, "type">)} />;
    case "relationship":
      return <RelationshipField {...props} />;
    default:
      warnUnexpectedType(type);
      return null;
  }
};

export default DynamicForm;

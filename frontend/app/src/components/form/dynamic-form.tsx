import { Button } from "@/components/buttons/button-primitive";
import CheckboxField from "@/components/form/fields/checkbox.field";
import ColorField from "@/components/form/fields/color.field";
import DatetimeField from "@/components/form/fields/datetime.field";
import DropdownField from "@/components/form/fields/dropdown.field";
import EnumField from "@/components/form/fields/enum.field";
import InputField from "@/components/form/fields/input.field";
import JsonField from "@/components/form/fields/json.field";
import ListField from "@/components/form/fields/list.field";
import NumberField from "@/components/form/fields/number.field";
import PasswordInputField from "@/components/form/fields/password-input.field";
import RelationshipField from "@/components/form/fields/relationship.field";
import TextareaField from "@/components/form/fields/textarea.field";
import { DynamicFieldProps, FormFieldValue } from "@/components/form/type";
import { Form, FormProps, FormRef, FormSubmit } from "@/components/ui/form";
import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import { warnUnexpectedType } from "@/utils/common";
import { forwardRef } from "react";

export interface DynamicFormProps extends Omit<FormProps, "onSubmit"> {
  fields: Array<DynamicFieldProps>;
  onCancel?: () => void;
  submitLabel?: string;
  onSubmit?: (data: Record<string, FormFieldValue>) => void;
}

const DynamicForm = forwardRef<FormRef, DynamicFormProps>(
  ({ fields, onCancel, submitLabel, ...props }, ref) => {
    const formDefaultValues = fields.reduce(
      (acc, field) => ({ ...acc, [field.name]: field.defaultValue }),
      {}
    );

    return (
      <Form ref={ref} {...props} defaultValues={formDefaultValues}>
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
  }
);

export const DynamicInput = (props: DynamicFieldProps) => {
  switch (props.type) {
    case SCHEMA_ATTRIBUTE_KIND.DATETIME: {
      const { type, ...otherProps } = props;
      return <DatetimeField {...otherProps} />;
    }
    case SCHEMA_ATTRIBUTE_KIND.COLOR: {
      const { type, ...otherProps } = props;
      return <ColorField {...otherProps} />;
    }
    case SCHEMA_ATTRIBUTE_KIND.BOOLEAN:
    case SCHEMA_ATTRIBUTE_KIND.CHECKBOX: {
      const { type, ...otherProps } = props;
      return <CheckboxField {...otherProps} />;
    }
    case SCHEMA_ATTRIBUTE_KIND.DROPDOWN: {
      const { type, ...otherProps } = props;
      return <DropdownField {...otherProps} />;
    }
    case SCHEMA_ATTRIBUTE_KIND.JSON: {
      const { type, ...otherProps } = props;
      return <JsonField {...otherProps} />;
    }
    case SCHEMA_ATTRIBUTE_KIND.LIST: {
      const { type, ...otherProps } = props;
      return <ListField {...otherProps} />;
    }
    case SCHEMA_ATTRIBUTE_KIND.BANDWIDTH:
    case SCHEMA_ATTRIBUTE_KIND.NUMBER: {
      const { type, ...otherProps } = props;
      return <NumberField {...otherProps} />;
    }
    case SCHEMA_ATTRIBUTE_KIND.PASSWORD:
    case SCHEMA_ATTRIBUTE_KIND.HASHED_PASSWORD: {
      const { type, ...otherProps } = props;
      return <PasswordInputField {...otherProps} />;
    }
    case SCHEMA_ATTRIBUTE_KIND.ANY:
    case SCHEMA_ATTRIBUTE_KIND.EMAIL:
    case SCHEMA_ATTRIBUTE_KIND.FILE:
    case SCHEMA_ATTRIBUTE_KIND.ID:
    case SCHEMA_ATTRIBUTE_KIND.IP_HOST:
    case SCHEMA_ATTRIBUTE_KIND.IP_NETWORK:
    case SCHEMA_ATTRIBUTE_KIND.MAC_ADDRESS:
    case SCHEMA_ATTRIBUTE_KIND.TEXT:
    case SCHEMA_ATTRIBUTE_KIND.URL: {
      const { type, ...otherProps } = props;
      return <InputField {...otherProps} />;
    }
    case SCHEMA_ATTRIBUTE_KIND.TEXTAREA: {
      const { type, ...otherProps } = props;
      return <TextareaField {...otherProps} />;
    }
    case "enum": {
      const { type, ...otherProps } = props;
      return <EnumField {...otherProps} />;
    }
    case "relationship": {
      return <RelationshipField {...props} />;
    }
    default: {
      warnUnexpectedType(props);
      return null;
    }
  }
};

export default DynamicForm;

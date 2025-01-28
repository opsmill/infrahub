import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { isHierarchicalSchema } from "@/entities/schema/utils";
import { Button } from "@/shared/components/buttons/button-primitive";
import CheckboxField from "@/shared/components/form/fields/checkbox.field";
import ColorField from "@/shared/components/form/fields/color.field";
import DatetimeField from "@/shared/components/form/fields/datetime.field";
import DropdownField from "@/shared/components/form/fields/dropdown.field";
import EnumField from "@/shared/components/form/fields/enum.field";
import InputField from "@/shared/components/form/fields/input.field";
import JsonField from "@/shared/components/form/fields/json.field";
import ListField from "@/shared/components/form/fields/list.field";
import NumberField from "@/shared/components/form/fields/number.field";
import PasswordInputField from "@/shared/components/form/fields/password-input.field";
import RelationshipHierarchicalField from "@/shared/components/form/fields/relationship-hierarchical.field";
import RelationshipManyField from "@/shared/components/form/fields/relationship-many.field";
import RelationshipField from "@/shared/components/form/fields/relationship.field";
import TextareaField from "@/shared/components/form/fields/textarea.field";
import { DynamicFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { Form, FormProps, FormRef, FormSubmit } from "@/shared/components/ui/form";
import { warnUnexpectedType } from "@/shared/utils/common";
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
      const { schema: peerSchema } = getSchema(props.relationship.peer);
      console.log("props: ", props);

      if (peerSchema && isHierarchicalSchema(peerSchema)) {
        return <RelationshipHierarchicalField {...props} />;
      }

      if (props.relationship.cardinality === "many") {
        const { type, ...otherProps } = props;
        return <RelationshipManyField {...otherProps} />;
      }

      return <RelationshipField {...props} />;
    }
    default: {
      warnUnexpectedType(props);
      return null;
    }
  }
};

export default DynamicForm;

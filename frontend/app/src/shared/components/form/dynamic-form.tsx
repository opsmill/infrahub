import { forwardRef } from "react";

import CheckboxField from "@/shared/components/form/fields/checkbox.field";
import ColorField from "@/shared/components/form/fields/color.field";
import DatetimeField from "@/shared/components/form/fields/datetime.field";
import DropdownField from "@/shared/components/form/fields/dropdown.field";
import EnumField from "@/shared/components/form/fields/enum.field";
import InputField from "@/shared/components/form/fields/input.field";
import JsonField from "@/shared/components/form/fields/json.field";
import ListField from "@/shared/components/form/fields/list.field";
import { NodeKindField } from "@/shared/components/form/fields/node-kind.field";
import NumberField from "@/shared/components/form/fields/number.field";
import PasswordInputField from "@/shared/components/form/fields/password-input.field";
import RelationshipField from "@/shared/components/form/fields/relationships/relationship.field";
import RelationshipHierarchicalField from "@/shared/components/form/fields/relationships/relationship-hierarchical.field";
import RelationshipManyField from "@/shared/components/form/fields/relationships/relationship-many.field";
import { SelectField } from "@/shared/components/form/fields/select.field";
import TextareaField from "@/shared/components/form/fields/textarea.field";
import type { DynamicFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { Button } from "@/shared/components/ui/button";
import { Form, type FormProps, type FormRef, FormSubmit } from "@/shared/components/ui/form";
import { warnUnexpectedType } from "@/shared/utils/common";

import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { isHierarchicalSchema } from "@/entities/schema/utils/is-hierarchical-schema";

export interface DynamicFormProps extends Omit<FormProps, "onSubmit"> {
  isBulkUpdate?: boolean;
  fields: Array<DynamicFieldProps>;
  onCancel?: () => void;
  submitLabel?: string;
  onSubmit?: (data: Record<string, FormFieldValue>) => void;
}

const DynamicForm = forwardRef<FormRef, DynamicFormProps>(
  ({ fields, onCancel, submitLabel, isBulkUpdate, ...props }, ref) => {
    const formDefaultValues = fields.reduce(
      (acc, field) => ({ ...acc, [field.name]: field.defaultValue }),
      {}
    );

    return (
      <Form ref={ref} {...props} defaultValues={formDefaultValues}>
        {fields.map((field) => (
          <DynamicField key={`${field.type}_${field.name}`} {...field} />
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

export const DynamicField = (props: DynamicFieldProps) => {
  switch (props.type) {
    case ATTRIBUTE_KIND.DATETIME: {
      const { type, ...otherProps } = props;
      return <DatetimeField {...otherProps} />;
    }
    case ATTRIBUTE_KIND.COLOR: {
      const { type, ...otherProps } = props;
      return <ColorField {...otherProps} />;
    }
    case ATTRIBUTE_KIND.BOOLEAN:
    case ATTRIBUTE_KIND.CHECKBOX: {
      const { type, ...otherProps } = props;
      return <CheckboxField {...otherProps} />;
    }
    case ATTRIBUTE_KIND.DROPDOWN: {
      const { type, ...otherProps } = props;
      return <DropdownField {...otherProps} />;
    }
    case ATTRIBUTE_KIND.JSON: {
      const { type, ...otherProps } = props;
      return <JsonField {...otherProps} />;
    }
    case ATTRIBUTE_KIND.LIST: {
      const { type, ...otherProps } = props;
      return <ListField {...otherProps} />;
    }
    case ATTRIBUTE_KIND.BANDWIDTH:
    case ATTRIBUTE_KIND.NUMBER: {
      const { type, ...otherProps } = props;
      return <NumberField {...otherProps} />;
    }
    case ATTRIBUTE_KIND.PASSWORD:
    case ATTRIBUTE_KIND.HASHED_PASSWORD: {
      const { type, ...otherProps } = props;
      return <PasswordInputField {...otherProps} />;
    }
    case ATTRIBUTE_KIND.ANY:
    case ATTRIBUTE_KIND.EMAIL:
    case ATTRIBUTE_KIND.FILE:
    case ATTRIBUTE_KIND.ID:
    case ATTRIBUTE_KIND.IP_HOST:
    case ATTRIBUTE_KIND.IP_NETWORK:
    case ATTRIBUTE_KIND.MAC_ADDRESS:
    case ATTRIBUTE_KIND.TEXT:
    case ATTRIBUTE_KIND.URL: {
      const { type, ...otherProps } = props;
      return <InputField {...otherProps} />;
    }
    case ATTRIBUTE_KIND.TEXTAREA: {
      const { type, ...otherProps } = props;
      return <TextareaField {...otherProps} />;
    }
    case "enum": {
      const { type, ...otherProps } = props;
      return <EnumField {...otherProps} />;
    }
    case "select": {
      const { type, ...otherProps } = props;
      return <SelectField {...otherProps} />;
    }
    case "relationship-add":
    case "relationship-remove":
    case "relationship": {
      const { schema: peerSchema } = getSchema(props.relationship.peer);

      if (peerSchema && isHierarchicalSchema(peerSchema)) {
        return <RelationshipHierarchicalField {...props} />;
      }

      if (props.relationship.cardinality === "many") {
        return <RelationshipManyField {...props} />;
      }

      return <RelationshipField {...props} />;
    }
    case ATTRIBUTE_KIND.NODE_KIND: {
      return <NodeKindField {...props} />;
    }
    default: {
      warnUnexpectedType(props);
      return null;
    }
  }
};

export default DynamicForm;

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import type {
  FormAttributeValue,
  FormFieldProps,
  FormRelationshipValue,
} from "@/shared/components/form/type";
import { FormField, FormMessage } from "@/shared/components/ui/form";

export type BulkUpdateUniqueFieldProps = Pick<
  FormFieldProps,
  "name" | "label" | "description" | "unique" | "shouldUnregister"
> & {
  defaultValue?: FormAttributeValue | FormRelationshipValue;
};

/**
 * Bulk-update presentation for a unique + optional attribute. A shared value cannot be applied
 * across every selected row without breaking uniqueness, so only the "Set empty" reset action is
 * offered -- there is no value input.
 */
const BulkUpdateUniqueField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  description,
  label,
  name,
  unique,
  shouldUnregister,
}: BulkUpdateUniqueFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      defaultValue={defaultValue}
      shouldUnregister={shouldUnregister}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value ?? DEFAULT_FORM_FIELD_VALUE;

        return (
          <div className="space-y-2">
            <div className="flex items-start justify-between gap-2">
              <LabelFormField
                label={label}
                unique={unique}
                description={description}
                fieldData={fieldData}
              />

              <ResetAction field={field} defaultValue={defaultValue} />
            </div>

            <p className="text-gray-600 text-xs">
              Unique values can only be cleared in bulk, not replaced.
            </p>

            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default BulkUpdateUniqueField;

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import type {
  DynamicRelationshipFieldProps,
  FormRelationshipValue,
} from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import { updateRelationshipFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { RelationshipManyInput } from "@/shared/components/inputs/relationship-many";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { classNames } from "@/shared/utils/common";

import type { NodeCore } from "@/entities/nodes/types";

export interface RelationshipManyInputProps extends DynamicRelationshipFieldProps {}

export default function RelationshipManyField({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  type,
  isBulkUpdate,
  relationship,
  description,
  label,
  name,
  rules,
  unique,
  shouldUnregister,
  ...props
}: RelationshipManyInputProps) {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      shouldUnregister={shouldUnregister}
      render={({ field, fieldState }) => {
        const fieldData: FormRelationshipValue = field.value;
        const { error } = fieldState;

        return (
          <div className="flex flex-col gap-2">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
              fieldData={fieldData}
            />

            <FormInput>
              <RelationshipManyInput
                {...field}
                {...props}
                className={classNames(
                  error &&
                    "has-[>:last-child:focus]:border-red-500 has-[>:last-child:focus]:ring-red-500/25"
                )}
                peer={relationship.peer}
                value={fieldData.value as NodeCore[] | null}
                onChange={(newValue) => {
                  field.onChange(
                    updateRelationshipFieldValue(
                      newValue.length > 0 ? newValue : null,
                      defaultValue
                    )
                  );
                }}
              />
            </FormInput>

            {canDisplayResetActions(relationship, isBulkUpdate) && type !== "relationship-add" && (
              <ResetAction field={field} defaultValue={defaultValue} />
            )}

            <FormMessage />
          </div>
        );
      }}
    />
  );
}

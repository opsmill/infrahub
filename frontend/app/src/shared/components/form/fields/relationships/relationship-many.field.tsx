import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import {
  DynamicRelationshipFieldProps,
  FormRelationshipValue,
} from "@/shared/components/form/type";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

import { NodeCore } from "@/entities/nodes/types";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { canRenderReset } from "@/shared/components/form/utils/canDisplayRestActions";
import { updateRelationshipFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { RelationshipManyInput } from "@/shared/components/inputs/relationship-many";
import { classNames } from "@/shared/utils/common";

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
  ...props
}: RelationshipManyInputProps) {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
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
                    "has-[>:last-child:focus]:ring-red-500/25 has-[>:last-child:focus]:border-red-500"
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

            {canRenderReset(relationship, isBulkUpdate) && type !== "relationship-add" && (
              <ResetAction field={field} defaultValue={defaultValue} />
            )}

            <FormMessage />
          </div>
        );
      }}
    />
  );
}

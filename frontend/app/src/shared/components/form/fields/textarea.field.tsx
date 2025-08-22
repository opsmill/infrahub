import { MarkdownEditor } from "@/shared/components/editor/markdown";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import { FormAttributeValue, FormFieldProps } from "@/shared/components/form/type";
import { canRenderReset } from "@/shared/components/form/utils/canDisplayRestActions";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { classNames } from "@/shared/utils/common";

const TextareaField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  isBulkUpdate,
  attribute,
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
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;

        return (
          <div>
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
              fieldData={fieldData}
              className="mb-2"
            />

            <FormInput>
              <MarkdownEditor
                {...field}
                {...props}
                className={classNames("w-full")}
                value={fieldData?.value as string | undefined}
                onChange={(newValue) => {
                  field.onChange(updateFormFieldValue(newValue, defaultValue));
                }}
              />
            </FormInput>

            {canRenderReset(attribute, isBulkUpdate) && (
              <ResetAction field={field} defaultValue={defaultValue} />
            )}

            <FormMessage className="mt-2" />
          </div>
        );
      }}
    />
  );
};

export default TextareaField;

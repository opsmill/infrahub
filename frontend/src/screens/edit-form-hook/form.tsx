import { MouseEventHandler, ReactElement } from "react";
import { FieldValues, FormProvider, SubmitHandler, useForm } from "react-hook-form";
import { BUTTON_TYPES, Button } from "../../components/button";
import { resolve } from "../../utils/objects";
import { DynamicControl } from "./dynamic-control";
import { DynamicFieldData } from "./dynamic-control-types";

type ErrorRef = {
  name?: string;
};

export type FormFieldError = {
  message?: string;
  ref?: ErrorRef;
  type?: string;
};

type FormFieldProps = {
  field: DynamicFieldData;
  error?: FormFieldError;
  disabled?: boolean;
};

export type FormProps = {
  fields: DynamicFieldData[];
  onSubmit: SubmitHandler<FieldValues>;
  onCancel?: MouseEventHandler<HTMLButtonElement> & Function;
  isLoading?: boolean;
  submitLabel?: string;
  disabled?: boolean;
  additionalButtons?: ReactElement;
  preventObjectsCreation?: boolean;
};

export const Form = ({
  fields,
  onSubmit,
  onCancel,
  isLoading,
  submitLabel = "Save",
  disabled,
  additionalButtons,
  preventObjectsCreation,
}: FormProps) => {
  const formMethods = useForm();

  const { handleSubmit, formState } = formMethods;

  const { errors } = formState;

  const FormField = (props: FormFieldProps) => {
    const { field, error, disabled } = props;

    return (
      <>
        <div className="sm:col-span-7">
          <DynamicControl
            {...field}
            error={error}
            disabled={disabled}
            preventObjectsCreation={preventObjectsCreation}
          />
        </div>
      </>
    );
  };

  const handleFormSubmit = (event: any) => {
    // Stop propagation for nested forms on related objects creation
    if (event && event.stopPropagation) {
      event.stopPropagation();
    }

    return handleSubmit(onSubmit)(event);
  };

  return (
    <form className="flex-1 flex flex-col w-full" data-cy="form">
      <FormProvider {...formMethods}>
        <div className="space-y-12 px-4 flex-1">
          <div className="">
            <div className="grid grid-cols-1 gap-x-6 sm:grid-cols-7 gap-y-4 py-4 md:grid-cols-4">
              {fields.map((field, index) => (
                <FormField
                  key={index}
                  field={field}
                  error={resolve(field.name, errors)}
                  disabled={disabled}
                />
              ))}
            </div>
          </div>
        </div>
        <div className="flex items-center justify-end gap-x-6 py-3 pr-3 border-t">
          {additionalButtons ?? null}

          {onCancel && <Button onClick={onCancel}>Cancel</Button>}

          <Button
            type="submit"
            data-cy="submit-form"
            onClick={handleFormSubmit}
            buttonType={BUTTON_TYPES.MAIN}
            isLoading={isLoading}
            disabled={disabled}>
            {submitLabel}
          </Button>
        </div>
      </FormProvider>
    </form>
  );
};

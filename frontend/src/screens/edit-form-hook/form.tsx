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

export type FormProps = {
  fields: DynamicFieldData[];
  onSubmit: SubmitHandler<FieldValues>;
  onCancel?: Function;
  isLoading?: boolean;
};

type FormFieldProps = {
  field: DynamicFieldData;
  error?: FormFieldError;
};

export const Form = ({ fields, onSubmit, onCancel, isLoading }: FormProps) => {
  const formMethods = useForm();
  const { handleSubmit, formState } = formMethods;

  const { errors } = formState;

  const FormField = (props: FormFieldProps) => {
    const { field, error } = props;

    return (
      <>
        <div className="sm:col-span-7">
          <DynamicControl {...field} error={error} />
        </div>
      </>
    );
  };

  return (
    <form className="flex-1 flex flex-col bg-white" onSubmit={handleSubmit(onSubmit)}>
      <FormProvider {...formMethods}>
        <div className="space-y-12 max-w-lg px-4 flex-1 bg-white">
          <div className="pb-12">
            <div className="grid grid-cols-1 gap-x-6 sm:grid-cols-7 gap-y-4 py-6 md:grid-cols-4">
              {fields.map((field, index) => (
                <FormField key={index} field={field} error={resolve(field.name, errors)} />
              ))}
            </div>
          </div>
        </div>
        <div className="mt-6 flex items-center justify-end gap-x-6 py-3 max-w-lg pr-3 border-t">
          <Button
            onClick={() => {
              if (onCancel) {
                onCancel();
              }
            }}>
            Cancel
          </Button>
          <Button type="submit" buttonType={BUTTON_TYPES.MAIN} isLoading={isLoading}>
            Save
          </Button>
        </div>
      </FormProvider>
    </form>
  );
};

import {
  FieldValues,
  FormProvider,
  SubmitHandler,
  useForm
} from "react-hook-form";
import { DynamicControl } from "./dynamic-control";
import { DynamicFieldData } from "./dynamic-control-types";
import { BUTTON_TYPES, Button } from "../../components/button";

interface FormProps {
  fields: DynamicFieldData[];
  onSubmit: SubmitHandler<FieldValues>;
  onCancel?: Function;
}

interface FormFieldProps {
  field: DynamicFieldData;
}

export const Form = ({ fields, onSubmit, onCancel }: FormProps) => {
  const formMethods = useForm();
  const {
    handleSubmit,
    // formState,
  } = formMethods;
  // console.log("formState?.errors: ", formState?.errors);

  const FormField = (props: FormFieldProps) => {
    const { field } = props;
    return <>
      <div className="sm:col-span-7">
        <DynamicControl {...field} />
      </div>
    </>;
  };

  return <form className="flex-1 flex flex-col" onSubmit={handleSubmit(onSubmit)}>
    <FormProvider {...formMethods}>
      <div className="space-y-12 max-w-lg px-4 flex-1 bg-white">
        <div className="pb-12">
          <div className="grid grid-cols-1 gap-x-6 sm:grid-cols-7 gap-y-4 py-6">
            {
              fields
              .map(
                (d, i) => (
                  <FormField key={i} field={d} />
                )
              )
            }
          </div>
        </div>
      </div>
      <div className="mt-6 flex items-center justify-end gap-x-6 py-3 max-w-lg pr-3 border-t">
        <Button onClick={
          () => {
            if(onCancel) {
              onCancel();
            }
          }
        }>
          Cancel
        </Button>
        <Button type="submit" buttonType={BUTTON_TYPES.MAIN}>
          Save
        </Button>
      </div>
    </FormProvider>
  </form>;
};

import { ErrorMessage } from "@hookform/error-message";
import {
  FieldValues,
  FormProvider,
  SubmitHandler,
  useForm
} from "react-hook-form";
import { DynamicControl, DynamicControlMetadata } from "./dynamic-control";
import { DynamicFieldData } from "./dynamic-control-types";

interface FormProps {
  fields: DynamicFieldData[];
  onSubmit: SubmitHandler<FieldValues>;
}

export const Form = ({ fields, onSubmit }: FormProps) => {
  const formMethods = useForm();

  const {
    handleSubmit,
    formState: { errors },
  } = formMethods;

  const FormField = ({ d, i }: any) => {
    return (
      <div className="sm:pt-5">
        <div className="text-red-500 text-xs">
          <ErrorMessage errors={errors} name={d.fieldName} />
        </div>
        <div key={i} className="sm:grid sm:grid-cols-5 sm:items-start sm:gap-4">
          <label
            htmlFor={d.fieldName}
            className="block text-sm font-medium leading-6 text-gray-900 sm:pt-1.5"
          >
            {d.label}
          </label>
          <div className="mt-2 sm:col-span-2 sm:mt-0">
            <div className="flex max-w-lg rounded-md shadow-sm">
              <DynamicControl {...d} />
            </div>
          </div>
          <div className="mt-2 sm:col-span-2 sm:mt-0">
            <div className="flex max-w-lg rounded-md shadow-sm">
              <DynamicControlMetadata {...d} />
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <form className="space-y-8 pb-4" onSubmit={handleSubmit(onSubmit)}>
      <FormProvider {...formMethods}>
        <div className="space-y-8 divide-y divide-gray-200 sm:space-y-5">
          <div className="space-y-6 sm:space-y-5">
            <div>
              <h3 className="text-base font-semibold leading-6 text-gray-900">
                Object details
              </h3>
              {/* <p className="mt-1 max-w-2xl text-sm text-gray-500">
                Update details of the object
              </p> */}
            </div>

            <div className="space-y-6 sm:space-y-5 divide-y">
              {fields.map((d, i) => (
                <FormField key={i} d={d} i={i} />
              ))}
            </div>
          </div>
        </div>

        <div className="pt-5">
          <div className="flex justify-end gap-x-3">
            <button
              type="button"
              className="rounded-md bg-white py-2 px-3 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="inline-flex justify-center rounded-md bg-indigo-600 py-2 px-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
            >
              Save
            </button>
          </div>
        </div>
      </FormProvider>
    </form>
  );
};

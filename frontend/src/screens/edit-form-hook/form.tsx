import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/20/solid";
import { ErrorMessage } from "@hookform/error-message";
import { useState } from "react";
import {
  FieldValues,
  FormProvider,
  SubmitHandler,
  useForm
} from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { DynamicControl, MetaDataFields } from "./dynamic-control";
import { DynamicFieldData } from "./dynamic-control-types";

interface FormProps {
  fields: DynamicFieldData[];
  onSubmit: SubmitHandler<FieldValues>;
}

interface FormFieldProps {
  field: DynamicFieldData;
}

export const Form = ({ fields, onSubmit }: FormProps) => {
  const formMethods = useForm();
  const navigate = useNavigate();

  const {
    handleSubmit,
    formState: { errors },
  } = formMethods;

  const FormField = (props: FormFieldProps) => {
    const { field } = props;
    const [showMetaDetailFields, setShowMetaDetailFields] = useState(false);
    return <>
      <div className="sm:col-span-6">
        <div className="text-red-500 text-xs">
          <ErrorMessage errors={errors} name={field.fieldName} />
        </div>
        <label 
          htmlFor={field.fieldName} className="block text-sm font-medium leading-6 text-gray-900 mt-6">
          {field.label}
        </label>
        <div className="mt-2">
          <DynamicControl {...field} />
        </div>
      </div>
      <div className="sm:col-span-1 flex items-end">
        {!showMetaDetailFields && <ChevronRightIcon onClick={() => setShowMetaDetailFields(true)} className="w-6 h-6 mb-1.5 cursor-pointer text-gray-500" />}
        {showMetaDetailFields && <ChevronDownIcon onClick={() => setShowMetaDetailFields(false)}  className="w-6 h-6 mb-1.5 cursor-pointer text-gray-500" />}
      </div>
      {showMetaDetailFields && <>
        <MetaDataFields {...field} />
      </>
      }
    </>
  };

  return <form onSubmit={handleSubmit(onSubmit)}>
    <FormProvider {...formMethods}>
      <div className="space-y-12 max-w-lg px-4">
        <div className="border-b border-gray-900/10 pb-12">
          {/* <h2 className="text-base font-semibold leading-7 text-gray-900">Object Information</h2>
          <p className="mt-1 text-sm leading-6 text-gray-600">Put in all the object details below.</p> */}
          <div className="grid grid-cols-1 gap-x-6 sm:grid-cols-7">
            {fields.map((d, i) => (
              <FormField key={i} field={d} />
            ))}
          </div>
        </div>
      </div>
      <div className="mt-6 flex items-center justify-end gap-x-6 pb-5 max-w-lg pr-3">
        <button type="button" className="text-sm font-semibold leading-6 text-gray-900" onClick={() => navigate(-1)}>
          Cancel
        </button>
        <button
          type="submit"
          className="rounded-md bg-indigo-600 py-2 px-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
        >
          Save
        </button>
      </div>
    </FormProvider>
  </form>

};

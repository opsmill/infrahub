import {
  FieldValues,
  FormProvider,
  SubmitHandler,
  useForm
} from "react-hook-form";
import { DynamicControl } from "./dynamic-control";
import { DynamicFieldData } from "./dynamic-control-types";

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
    // formState: { errors },
  } = formMethods;

  const FormField = (props: FormFieldProps) => {
    const { field } = props;
    // const [showMetaDetailFields, setShowMetaDetailFields] = useState(false);
    return <>
      <div className="sm:col-span-7">
        {/* <div className="text-red-500 text-xs">
          <ErrorMessage errors={errors} name={field.name} />
        </div> */}
        {/* <label
          htmlFor={field.name} className="block text-sm font-medium leading-6 text-gray-900 mt-6">
          {field.label}
        </label> */}
        <DynamicControl {...field} />
        {/* <div className="mt-2">
        </div> */}
      </div>
      {/* <div className="sm:col-span-1 flex items-end"> */}
      {/* {!showMetaDetailFields && <ChevronRightIcon onClick={() => setShowMetaDetailFields(true)} className="w-6 h-6 mb-1.5 cursor-pointer text-gray-500" />}
        {showMetaDetailFields && <ChevronDownIcon onClick={() => setShowMetaDetailFields(false)}  className="w-6 h-6 mb-1.5 cursor-pointer text-gray-500" />} */}
      {/* </div> */}
      {/* {showMetaDetailFields && <>
        <MetaDataFields {...field} />
      </>
      } */}
    </>;
  };

  return <form className="flex-1 flex flex-col" onSubmit={handleSubmit(onSubmit)}>
    <FormProvider {...formMethods}>
      <div className="space-y-12 max-w-lg px-4 flex-1">
        <div className="pb-12">
          {/* <h2 className="text-base font-semibold leading-7 text-gray-900">Object Information</h2>
          <p className="mt-1 text-sm leading-6 text-gray-600">Put in all the object details below.</p> */}
          <div className="grid grid-cols-1 gap-x-6 sm:grid-cols-7 gap-y-4 py-6">
            {fields.map((d, i) => (
              <FormField key={i} field={d} />
            ))}
          </div>
        </div>
      </div>
      <div className="mt-6 flex items-center justify-end gap-x-6 py-3 max-w-lg pr-3 border-t">
        <button type="button" className="rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50" onClick={() => {
          if(onCancel) {
            onCancel();
          }
        }}>
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
  </form>;

};

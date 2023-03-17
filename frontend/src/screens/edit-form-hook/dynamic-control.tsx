import { useFormContext } from "react-hook-form";
import { DynamicFieldData } from "./dynamic-control-types";
import MultiSelect from "./multi-select";

export const DynamicControl = (props: DynamicFieldData) => {
  const {
    inputType,
    fieldName,
    defaultValue,
    options = [],
    config = {},
  } = props;
  const { register, control } = useFormContext();

  let input = <input type="text" />;

  switch (inputType) {
    case "text":
      input = (
        <input
          className="block w-full max-w-lg rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
          type="text"
          {...register(fieldName, config)}
          defaultValue={defaultValue}
        />
      );
      break;
    case "select": {
      input = (
        <select
          className="mt-2 block w-full rounded-md border-0 py-1.5 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6"
          {...register(fieldName, config)}
          defaultValue={defaultValue}
          name={fieldName}
          id={fieldName}
        >
          {options.map((o, index) => (
            <option key={index} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      );
      break;
    }
    case "multiselect": {
      const field = register(fieldName, config);
      input = (
        <MultiSelect
          options={options}
          control={control}
          onChange={field.onChange}
          {...props}
        />
      );
      break;
    }
    case "number":
      input = (
        <input
          type="number"
          {...register(fieldName, config)}
          defaultValue={defaultValue}
        />
      );
      break;
    default:
      input = <input type="text" />;
      break;
  }
  return input;
};

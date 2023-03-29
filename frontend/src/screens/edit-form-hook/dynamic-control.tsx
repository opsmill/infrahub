import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { useFormContext } from "react-hook-form";
import { schemaState } from "../../state/atoms/schema.atom";
import getDropdownOptionsForRelatedPeers, { iPeerDropdownOption } from "../../utils/dropdownOptionsForRelatedPeers";
import { DynamicFieldData, SelectOption } from "./dynamic-control-types";
import MultiSelect from "./multi-select";

export const DynamicControl = (props: DynamicFieldData) => {
  const {
    inputType,
    fieldName,
    defaultValue,
    isAttribute,
    isRelationship,
    relationshipCardinality,
    options = {
      values: [],
    },
    config = {},
  } = props;
  const { register, control } = useFormContext();

  let input = <input type="text" />;
  let name;

  if(isAttribute) {
    name = fieldName + ".value";
  } else if (isRelationship && relationshipCardinality === "one") {
    name = fieldName + ".id";
  } else {
    name = fieldName + ".list";
  }


  let value: any;
  if(!defaultValue) {
    value = "";
  } else {
    if(isAttribute) {
      value = defaultValue.value;
    } else if(relationshipCardinality === "many") {
      value = defaultValue.map((item: any) => item.id)
    } else {
      value = defaultValue.id
    }
  }

  switch (inputType) {
    case "text":
      input = (
        <input
          className="mt-2 block w-full max-w-lg rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
          type="text"
          {...register(name, config)}
          defaultValue={value}
        />
      );
      break;
    case "select": {
      input = (
        <select
          className="mt-2 block w-full rounded-md border-0 py-1.5 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6"
          {...register(name, config)}
          defaultValue={value}
          name={name}
          id={name}
        >
          {options.values.map((o, index) => (
            <option key={index} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      );
      break;
    }
    case "multiselect": {
      const def = options.values.filter(
        (option) => (value || []).indexOf(option.value) > -1
      );
      const field = register(name, {
        ...config,
        value: def,
      });
      // If user does not change anything in the multi-select dropdown, the field value in the form data remains undefined
      // Not a problem currently, as if nothing get's changed, we are not sending out that field in the update mutation
      // but something that we can look into later on
      input = (
        <MultiSelect
          {...props}
          fieldName={name}
          options={options.values}
          control={control}
          onChange={field.onChange}
        />
      );
      break;
    }
    case "number":
      input = (
        <input
          className="mt-2 block w-full max-w-lg rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
          type="number"
          {...register(name, {
            valueAsNumber: true,
          })}
          defaultValue={value}
        />
      );
      break;
    default:
      input = <input type="text" />;
      break;
  }
  return input;
};

export const DynamicControlMetadata = (props: DynamicFieldData) => {
  const {
    fieldName,
    isAttribute,
    defaultValue,
  } = props;
  const { register } = useFormContext();
  const [schemaList] = useAtom(schemaState);

  const schemaOptions: SelectOption[] = [{
    label: "",
    value: "",
  }, ...schemaList.map(schema => ({
    label: schema.kind,
    value: schema.name,
  }))]

  const [relatedItemOptions, setRelatedItemOptions] = useState<iPeerDropdownOption[]>([]);

  let metaAttribute;

  if(isAttribute) {
    metaAttribute = "owner";
  } else {
    metaAttribute = "_relation__owner";
  }

  const name = fieldName + "." + metaAttribute;
  const metaField = defaultValue[metaAttribute];

  const [objectKindname, setObjectKindName] = useState(metaField ? metaField.__typename : "");

  const setDropdownOptions = useCallback(async () => {
    const schema = schemaList.filter(schema => schema.kind === objectKindname);
    if(schema.length) {
      const objectName = schema[0].name;
      const peerDropdownOptions = await getDropdownOptionsForRelatedPeers([objectName]);
      const options = peerDropdownOptions[objectName];
      setRelatedItemOptions(options);
    }
  }, [objectKindname, schemaList]);

  useEffect(() => {
    setDropdownOptions();
  }, [objectKindname, setDropdownOptions]);

  return <div className="flex">
    <div>
      <select
        className="mt-2 block w-full rounded-md border-0 py-1.5 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6"
        defaultValue={objectKindname}
        onChange={(e) => setObjectKindName(e.target.value)}
      >
        {schemaOptions.map((o, index) => (
          <option key={index} value={o.label}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
    <div>
      {relatedItemOptions.length > 0 && <select
        className="mt-2 block w-full rounded-md border-0 py-1.5 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6"
        {...register(name, {
          value: metaField ? metaField.id : "",
        })}
      >
        {relatedItemOptions.map((o, index) => (
          <option key={index} value={o.id}>
            {o.id.slice(0, 10)} {o.display_label}
          </option>
        ))}
      </select>}
    </div>
  </div>
};

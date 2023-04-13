import { useFormContext } from "react-hook-form";
import { OpsInputRegister } from "../../components-form/input.register";
import { OpsMultiSelectRegister } from "../../components-form/multi-select.register";
import { OpsSelect2StepRegister } from "../../components-form/select-2-step.register";
import { OpsSelectRegister } from "../../components-form/select.register";
import { OpsSwitchRegister } from "../../components-form/switch.register";
import { ControlType, DynamicFieldData } from "./dynamic-control-types";

export const DynamicControl = (props: DynamicFieldData) => {
  const {
    type,
    name,
    label,
    kind,
    value,
    options = {
      values: [],
    },
    config = {},
  } = props;
  const { register, setValue } = useFormContext();

  const getFormFieldByInputType = (inputType: ControlType) => {
    switch (inputType) {
      case "text":
        return <OpsInputRegister label={label} config={config} register={register} setValue={setValue} name={name} value={value} />;
      case "number":
        config.valueAsNumber = true;
        return <OpsInputRegister label={label} config={config} register={register} setValue={setValue} name={name} value={value} />;
      case "checkbox":
        return <OpsSwitchRegister label={label} config={config} register={register} setValue={setValue} name={name} value={value} />;
      case "select2step": {
        const selectOptions = options.values.map(o => ({
          label: o.name,
          value: o.id,
        }));
        return <OpsSelect2StepRegister register={register} name={name} config={config} options={selectOptions} value={{ parent: value?.__typename, child: value?.id}} label={label} setValue={setValue} />;
      }
      case "select": {
        if(["Integer", "Number", "Bandwidth"].indexOf(kind) > -1) {
          config.valueAsNumber = true;
        }
        return <OpsSelectRegister options={options.values} config={config} register={register} setValue={setValue} name={name} value={value} />;
      }
      case "multiselect": {
        const multiSelectOptions = options.values.map(o => ({
          label: o.name,
          value: o.id,
        }));

        const currentValue = multiSelectOptions.filter(
          (option) => (value || []).indexOf(option.value) > -1
        );

        return <OpsMultiSelectRegister label={label} config={config} register={register} setValue={setValue} options={multiSelectOptions} name={name} value={currentValue} />;
        // If user does not change anything in the multi-select dropdown, the field value in the form data remains undefined
        // Not a problem currently, as if nothing get's changed, we are not sending out that field in the update mutation
        // but something that we can look into later on
      }
      default:
        return <input type="text" />;
    }
  };

  return getFormFieldByInputType(type);
};

// interface iSourceOwnerFieldProps {
//   field: DynamicFieldData;
//   metaFieldName: string;
// }

// export const SourceOwnerField = (props: iSourceOwnerFieldProps) => {
//   const {
//     field,
//     metaFieldName,
//   } = props;
//   const { register } = useFormContext();
//   const [schemaList] = useAtom(schemaState);

//   const relatedObjects: { [key: string]: string; } = {
//     "source": "DataSource",
//     "owner": "DataOwner",
//     "_relation__source": "DataSource",
//     "_relation__owner": "DataOwner",
//   };

//   const schemaOptions: SelectOption[] = [{
//     label: "",
//     value: "",
//   }, ...schemaList.filter(schema => {
//     if((schema.inherit_from || []).indexOf(relatedObjects[metaFieldName]) > -1) {
//       return true;
//     } else {
//       return false;
//     }
//   }).map(schema => ({
//     label: schema.kind,
//     value: schema.name,
//   }))];

//   const [relatedItemOptions, setRelatedItemOptions] = useState<iPeerDropdownOption[]>([]);

//   const name = field.name + "." + metaFieldName;
//   const metaFieldObject = field.value[metaFieldName];

//   const [objectKindname, setObjectKindName] = useState(metaFieldObject ? metaFieldObject.__typename : "");

//   const setDropdownOptions = useCallback(async () => {
//     const schema = schemaList.filter(schema => schema.kind === objectKindname);
//     if(schema.length) {
//       const objectName = schema[0].name;
//       const peerDropdownOptions = await getDropdownOptionsForRelatedPeers([objectName]);
//       const options = peerDropdownOptions[objectName];
//       setRelatedItemOptions(options);
//     }
//   }, [objectKindname, schemaList]);

//   useEffect(() => {
//     setDropdownOptions();
//   }, [objectKindname, setDropdownOptions]);

//   return <>
//     <div className="sm:col-span-1"></div>
//     <div className="sm:col-span-6">
//       <label
//         className="block text-sm font-medium leading-6 text-gray-900 capitalize mt-4 mb-2">
//         {metaFieldName.split("_").filter(r => !!r).join(" ")}
//       </label>
//     </div>
//     <div className="sm:col-span-1"></div>
//     <div className="sm:col-span-3">
//       <select
//         className="block w-full rounded-md border-0 py-1.5 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6"
//         defaultValue={objectKindname}
//         placeholder="Choose Type"
//         onChange={(e) => setObjectKindName(e.target.value)}
//       >
//         {schemaOptions.map((o, index) => (
//           <option key={index} value={o.label}>
//             {o.label}
//           </option>
//         ))}
//       </select>
//     </div>
//     <div className="sm:col-span-3">
//       {relatedItemOptions.length > 0 && <select
//         className="block w-full rounded-md border-0 py-1.5 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6"
//         {...register(name, {
//           value: metaFieldObject ? metaFieldObject.id : "",
//         })}
//       >
//         {relatedItemOptions.map((o, index) => (
//           <option key={index} value={o.id}>
//             {o.display_label}
//           </option>
//         ))}
//       </select>}
//     </div>

//   </>;
// };

// export const MetaToggleField = (props: iSourceOwnerFieldProps) => {
//   const {
//     field,
//     metaFieldName,
//   } = props;
//   const { register } = useFormContext();

//   const name = field.name + "." + metaFieldName;
//   const metaFieldValue = field.value[metaFieldName];

//   return <>
//     <div className="sm:col-span-1"></div>
//     <div className="sm:col-span-6">
//       <label
//         className="block text-sm font-medium leading-6 text-gray-900 capitalize mt-4 mb-2">
//         {metaFieldName.split("_").filter(r => !!r).join(" ")}
//       </label>
//     </div>
//     <div className="sm:col-span-1"></div>
//     <div className="sm:col-span-6">
//       <input type="checkbox" {...register(name, {
//         value: metaFieldValue,
//       })} />
//     </div>
//   </>;
// };

// export const MetaDataFields = (props: DynamicFieldData) => {
//   const {
//     isAttribute,
//   } = props;

//   const sourceOwnerFields = isAttribute ? ["owner", "source"] : ["_relation__owner", "_relation__source"];
//   const booleanFields = isAttribute ? ["is_visible", "is_protected"] : ["_relation__is_visible", "_relation__is_protected"];

//   return <>
//     {booleanFields.map(field => <MetaToggleField field={props} metaFieldName={field} key={field} />)}
//     {sourceOwnerFields.map(sourceOwnerField => <SourceOwnerField field={props} metaFieldName={sourceOwnerField} key={sourceOwnerField} />)}
//   </>;
// };

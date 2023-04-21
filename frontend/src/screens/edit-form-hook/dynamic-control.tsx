import { useFormContext } from "react-hook-form";
import { OpsInputRegister } from "../../components-form/input.register";
import { OpsMultiSelectRegister } from "../../components-form/multi-select.register";
import { OpsSelect2StepRegister } from "../../components-form/select-2-step.register";
import { OpsSelectRegister } from "../../components-form/select.register";
import { OpsSwitchRegister } from "../../components-form/switch.register";
import { ControlType, DynamicFieldData } from "./dynamic-control-types";
import { OpsCheckboxRegister } from "../../components-form/checkbox.register";

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
      case "switch":
        return <OpsSwitchRegister label={label} config={config} register={register} setValue={setValue} name={name} value={value} />;
      case "checkbox":
        return <OpsCheckboxRegister label={label} config={config} register={register} setValue={setValue} name={name} value={value} />;
      case "select": {
        if(["Integer", "Number", "Bandwidth"].indexOf(kind) > -1) {
          config.valueAsNumber = true;
        }
        return <OpsSelectRegister label={label} options={options.values} config={config} register={register} setValue={setValue} name={name} value={value} />;
      }
      case "select2step": {
        const selectOptions = options.values.map(o => ({
          name: o.name,
          id: o.id,
        }));
        const regex = /^Related/; // starts with Related
        return <OpsSelect2StepRegister register={register} name={name} config={config} options={selectOptions} value={{ parent: value?.__typename?.replace(regex, ""), child: value?.id}} label={label} setValue={setValue} />;
      }
      case "multiselect": {
        const currentValue = options
        .values
        .filter(
          (option) => (value || []).indexOf(option.id) > -1
        );

        return <OpsMultiSelectRegister label={label} config={config} register={register} setValue={setValue} options={options.values} name={name} value={currentValue} />;
        // If user does not change anything in the multi-select dropdown, the field value in the form data remains undefined
        // Not a problem currently, as if nothing get's changed, we are not sending out that field in the update mutation
        // but something that we can look into later on
      }
      default:
        return null;
    }
  };

  return getFormFieldByInputType(type);
};
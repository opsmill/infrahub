import { useFormContext } from "react-hook-form";
import { OpsCheckboxRegister } from "../../components-form/checkbox.register";
import { OpsDatePickerRegister } from "../../components-form/date-picker.register";
import { OpsInputRegister } from "../../components-form/input.register";
import { OpsMultiSelectRegister } from "../../components-form/multi-select.register";
import { OpsSelect2StepRegister } from "../../components-form/select-2-step.register";
import { OpsSelectRegister } from "../../components-form/select.register";
import { OpsSwitchRegister } from "../../components-form/switch.register";
import { OpsTextareaRegister } from "../../components-form/textarea.register";
import { ControlType, DynamicFieldData } from "./dynamic-control-types";

export const DynamicControl = (props: DynamicFieldData) => {
  const {
    type,
    name,
    kind,
    value,
    options = {
      values: [],
    },
    config = {},
  } = props;
  const { register, setValue, getValues } = useFormContext();

  const getFormFieldByInputType = (inputType: ControlType) => {
    const existingValue = getValues(name);

    switch (inputType) {
      case "text":
        return (
          <OpsInputRegister
            {...props}
            register={register}
            setValue={setValue}
            value={existingValue ?? value}
          />
        );
      case "textarea":
        return (
          <OpsTextareaRegister
            {...props}
            register={register}
            setValue={setValue}
            value={existingValue ?? value}
          />
        );
      case "number":
        config.valueAsNumber = true;
        return (
          <OpsInputRegister
            {...props}
            register={register}
            setValue={setValue}
            value={existingValue ?? value}
          />
        );
      case "switch":
        return (
          <OpsSwitchRegister
            {...props}
            register={register}
            setValue={setValue}
            value={existingValue ?? value}
          />
        );
      case "checkbox":
        return (
          <OpsCheckboxRegister
            {...props}
            register={register}
            setValue={setValue}
            value={existingValue ?? value}
          />
        );
      case "select": {
        if (kind && ["Integer", "Number", "Bandwidth"].indexOf(kind) > -1) {
          config.valueAsNumber = true;
        }
        return (
          <OpsSelectRegister
            {...props}
            options={options.values}
            register={register}
            setValue={setValue}
            value={existingValue ?? value}
          />
        );
      }
      case "select2step": {
        const selectOptions = options.values.map((o) => ({
          name: o.name,
          id: o.id,
        }));
        const regex = /^Related/; // starts with Related

        const selectValue = {
          parent: value?.__typename?.replace(regex, ""),
          child: value?.id,
        };

        return (
          <OpsSelect2StepRegister
            {...props}
            options={selectOptions}
            value={selectValue}
            register={register}
            setValue={setValue}
          />
        );
      }
      case "multiselect": {
        const currentValue = options.values.filter(
          (option) => (value || []).indexOf(option.id) > -1
        );

        return (
          <OpsMultiSelectRegister
            {...props}
            options={options.values}
            value={existingValue ?? currentValue}
            register={register}
            setValue={setValue}
          />
        );
        // If user does not change anything in the multi-select dropdown, the field value in the form data remains undefined
        // Not a problem currently, as if nothing get's changed, we are not sending out that field in the update mutation
        // but something that we can look into later on
      }
      case "datepicker": {
        return <OpsDatePickerRegister {...props} register={register} setValue={setValue} />;
      }
      default:
        return null;
    }
  };

  return getFormFieldByInputType(type);
};

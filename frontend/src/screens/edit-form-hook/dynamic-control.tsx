import { useFormContext } from "react-hook-form";
import { OpsCheckboxRegister } from "../../components-form/checkbox.register";
import { CodeEditorRegister } from "../../components-form/code-editor.register";
import { OpsDatePickerRegister } from "../../components-form/date-picker.register";
import { OpsInputRegister } from "../../components-form/input.register";
import { OpsListRegister } from "../../components-form/list.register";
import { OpsMultiSelectRegister } from "../../components-form/multi-select.register";
import { OpsSelect2StepRegister } from "../../components-form/select-2-step.register";
import { OpsSelectRegister } from "../../components-form/select.register";
import { OpsSwitchRegister } from "../../components-form/switch.register";
import { OpsTextareaRegister } from "../../components-form/textarea.register";
import { DynamicFieldData } from "./dynamic-control-types";

export const DynamicControl = (props: DynamicFieldData) => {
  const {
    type,
    name,
    // kind,
    value,
    options = {
      values: [],
    },
    // config = {},
  } = props;

  const { register, setValue, getValues } = useFormContext();

  const existingValue = getValues(name);

  switch (type) {
    case "password":
    case "text":
    case "number":
      return (
        <OpsInputRegister
          {...props}
          inputType={type}
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
    case "select":
      return (
        <OpsSelectRegister
          {...props}
          options={options.values}
          register={register}
          setValue={setValue}
          value={existingValue ?? value}
        />
      );
    case "dropdown": {
      return (
        <OpsSelectRegister
          {...props}
          options={options.values}
          register={register}
          setValue={setValue}
          value={existingValue ?? value}
          dropdown
        />
      );
    }
    case "enum": {
      return (
        <OpsSelectRegister
          {...props}
          options={options.values}
          register={register}
          setValue={setValue}
          value={existingValue ?? value}
          enum
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
      const selectOptions = options?.values ?? value;

      const currentValue = selectOptions.filter((option) => (value || []).indexOf(option.id) > -1);

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
    case "list": {
      return <OpsListRegister {...props} register={register} setValue={setValue} />;
    }
    case "datepicker": {
      return (
        <OpsDatePickerRegister
          {...props}
          value={existingValue || value}
          register={register}
          setValue={setValue}
        />
      );
    }
    case "json": {
      const objectValue = existingValue ?? value;

      const jsonValue = typeof objectValue === "string" ? objectValue : JSON.stringify(objectValue);

      return (
        <CodeEditorRegister {...props} value={jsonValue} register={register} setValue={setValue} />
      );
    }
    default:
      return null;
  }
};

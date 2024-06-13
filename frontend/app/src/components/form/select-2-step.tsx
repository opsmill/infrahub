import { QuestionMark } from "@/components/display/question-mark";
import { SelectOption } from "@/components/inputs/select";
import { components } from "@/infraops";
import { FormFieldError } from "@/screens/edit-form-hook/form";
import { LockClosedIcon } from "@heroicons/react/24/outline";
import { useState } from "react";
import { OpsSelect } from "./select";

export interface iTwoStepDropdownData {
  parent: null | string | number;
  child: null | string | number;
}

interface Props {
  label: string;
  options: SelectOption[];
  value: iTwoStepDropdownData;
  onChange: (value: iTwoStepDropdownData) => void;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptional?: boolean;
  isInherited?: boolean;
  peer?: string;
  field:
    | components["schemas"]["AttributeSchema-Output"]
    | components["schemas"]["RelationshipSchema-Output"];
}

export const OpsSelect2Step = (props: Props) => {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, react/prop-types, no-unused-vars
  const { label, options, value, onChange, isOptional, peer, ...propsToPass } = props;
  const { isProtected, field } = props;

  const [selectedLeft, setSelectedLeft] = useState(
    value && value?.parent ? options.find((option) => option.id === value?.parent) : null
  );

  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-1.5">
        <label htmlFor={label} className="text-sm font-medium leading-6 text-gray-900">
          {label} {!isOptional && "*"}
        </label>
        {isProtected && <LockClosedIcon className="w-4 h-4" />}
        <QuestionMark message={field?.description} />
      </div>
      <div className="flex">
        <div className="sm:col-span-3 mr-2 mt-1">
          <OpsSelect
            {...propsToPass}
            value={selectedLeft?.id}
            options={options}
            label=""
            onChange={setSelectedLeft}
            data-cy="select2step-1"
            data-testid="select2step-1"
          />
        </div>
        <div className="sm:col-span-3 ml-2 mt-1">
          {!!selectedLeft && (
            <OpsSelect
              {...propsToPass}
              value={value?.child}
              options={[]}
              label=""
              onChange={onChange}
              peer={selectedLeft?.id}
              data-cy="select2step-2"
              data-testid="select2step-2"
            />
          )}
        </div>
      </div>
    </div>
  );
};

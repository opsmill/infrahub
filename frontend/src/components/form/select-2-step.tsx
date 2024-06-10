import { QuestionMark } from "@/components/display/question-mark";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { getDropdownOptions } from "@/graphql/queries/objects/dropdownOptions";
import { FormFieldError } from "@/screens/edit-form-hook/form";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { gql } from "@apollo/client";
import { LockClosedIcon } from "@heroicons/react/24/outline";
import { useAtomValue } from "jotai/index";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { components } from "../../infraops";
import { SelectOption } from "../inputs/select";
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

  const { objectid } = useParams();
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const [optionsRight, setOptionsRight] = useState([]);
  const [selectedLeft, setSelectedLeft] = useState(
    value && value?.parent ? options.find((option) => option.id === value?.parent) : null
  );

  const [selectedRight, setSelectedRight] = useState(
    value && value?.child ? optionsRight.find((option) => option.id === value?.child) : null
  );

  const setRightDropdownOptions = useCallback(async () => {
    if (!selectedLeft?.id) {
      return;
    }

    const queryString = getDropdownOptions({
      kind: selectedLeft.id,
    });

    const query = gql`
      ${queryString}
    `;

    const { data } = await graphqlClient.query({
      query,
      context: {
        date,
        branch: branch?.name,
      },
    });

    // Filter the options to not select the current object
    const newRigthOptions = data[selectedLeft.id]?.edges
      .map((edge: any) => edge.node)
      .filter((option: any) => option.id !== objectid)
      .map((option: any) => ({
        name: option.display_label,
        id: option.id,
      }));

    setOptionsRight(newRigthOptions);

    const rightOptionsIds = newRigthOptions.map((option: any) => option.id);

    if (value.child && rightOptionsIds.includes(value.child)) {
      return setSelectedRight({ id: value.child });
    }

    return setSelectedRight(null);
  }, [selectedLeft?.id]);

  useEffect(() => {
    setRightDropdownOptions();
  }, [selectedLeft?.id]);

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
          {!!selectedLeft && optionsRight.length > 0 && (
            <OpsSelect
              {...propsToPass}
              value={selectedRight?.id}
              options={optionsRight}
              label=""
              onChange={(value) => {
                setSelectedRight(value);
                onChange({
                  parent: selectedLeft?.id,
                  child: value,
                });
              }}
              data-cy="select2step-2"
              data-testid="select2step-2"
            />
          )}
        </div>
      </div>
    </div>
  );
};

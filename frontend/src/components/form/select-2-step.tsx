import { gql } from "@apollo/client";
import { LockClosedIcon } from "@heroicons/react/24/outline";
import { useAtomValue } from "jotai/index";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { getDropdownOptions } from "../../graphql/queries/objects/dropdownOptions";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { SelectOption } from "../inputs/select";
import { OpsSelect } from "./select";

export interface iTwoStepDropdownData {
  parent: string | number;
  child: string | number;
}

interface Props {
  label: string;
  options: SelectOption[];
  value: string | iTwoStepDropdownData;
  onChange: (value: iTwoStepDropdownData) => void;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptional?: boolean;
  isInherited?: boolean;
  peer?: string;
}

export const OpsSelect2Step = (props: Props) => {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, react/prop-types, no-unused-vars
  const { label, options, value, onChange, isOptional, peer, ...propsToPass } = props;
  const { isProtected } = props;

  const { objectid } = useParams();
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const [optionsRight, setOptionsRight] = useState([]);

  const [selectedLeft, setSelectedLeft] = useState(
    value && value?.parent ? options.find((option) => option.id === value?.parent)?.id : null
  );

  const [selectedRight, setSelectedRight] = useState(
    value && value?.child ? optionsRight.find((option) => option.id === value?.child)?.id : null
  );

  const setRightDropdownOptions = useCallback(async () => {
    if (!selectedLeft) {
      return;
    }

    const queryString = getDropdownOptions({
      kind: selectedLeft,
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

    const newRigthOptions = data[selectedLeft]?.edges.map((edge: any) => edge.node);

    setOptionsRight(
      newRigthOptions
        // Filter the options to not select the current object
        .filter((option: any) => option.id !== objectid)
        .map((option: any) => ({
          name: option.display_label,
          id: option.id,
        }))
    );

    if (value.child) {
      setSelectedRight(value.child);
    }
  }, [selectedLeft]);

  useEffect(() => {
    setRightDropdownOptions();
  }, [selectedLeft]);

  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-1.5">
        <label htmlFor={label} className="text-sm font-medium leading-6 text-gray-900">
          {label} {!isOptional && "*"}
        </label>
        {isProtected && <LockClosedIcon className="w-4 h-4" />}
      </div>
      <div className="flex">
        <div className="sm:col-span-3 mr-2 mt-1">
          <OpsSelect
            {...propsToPass}
            value={selectedLeft}
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
              value={selectedRight}
              options={optionsRight}
              label=""
              onChange={(value) => {
                setSelectedRight(value);
                onChange({
                  parent: selectedLeft,
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

import { useAtomValue } from "jotai/index";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { classNames } from "../../utils/common";
import { SelectOption } from "../inputs/select";
import { OpsSelect } from "./select";
import { getDropdownOptions } from "../../graphql/queries/objects/dropdownOptions";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { gql } from "@apollo/client";

export interface iTwoStepDropdownData {
  parent: string | number;
  child: string | number;
}

interface Props {
  label: string;
  options: SelectOption[];
  value: iTwoStepDropdownData;
  onChange: (value: iTwoStepDropdownData) => void;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptional?: boolean;
}

export const OpsSelect2Step = (props: Props) => {
  const { label, options, value, error, onChange, isProtected, isOptional } = props;

  const { objectid } = useParams();
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const [optionsRight, setOptionsRight] = useState([]);

  const [selectedLeft, setSelectedLeft] = useState(
    value.parent ? options.find((option) => option.id === value.parent)?.id : null
  );

  const [selectedRight, setSelectedRight] = useState(
    value.child ? optionsRight.find((option) => option.id === value.child)?.id : null
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
    <div className={classNames("grid grid-cols-6")}>
      <div className="sm:col-span-6">
        <label className="block text-sm font-medium leading-6 text-gray-900 capitalize">
          {label} {isOptional ? "" : "*"}
        </label>
      </div>
      <div className="sm:col-span-3 mr-2 mt-1">
        <OpsSelect
          error={error}
          disabled={false}
          value={selectedLeft}
          options={options}
          label=""
          onChange={setSelectedLeft}
          isProtected={isProtected}
          data-cy="select2step-1"
          data-testid="select2step-1"
        />
      </div>
      <div className="sm:col-span-3 ml-2 mt-1">
        {!!selectedLeft && optionsRight.length > 0 && (
          <OpsSelect
            error={error}
            disabled={false}
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
            isProtected={isProtected}
            data-cy="select2step-2"
            data-testid="select2step-2"
          />
        )}
      </div>
    </div>
  );
};

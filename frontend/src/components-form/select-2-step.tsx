import { gql } from "@apollo/client";
import { useCallback, useEffect, useState } from "react";
import { SelectOption } from "../components/select";
import graphqlClient from "../graphql/graphqlClientApollo";
import { FormFieldError } from "../screens/edit-form-hook/form";
import { classNames } from "../utils/common";
import { getDropdownOptionsForRelatedPeers } from "../utils/dropdownOptionsForRelatedPeers";
import { OpsSelect } from "./select";

export interface iTwoStepDropdownData {
  parent: string;
  child: string;
}

interface Props {
  label: string;
  options: SelectOption[];
  value: iTwoStepDropdownData;
  onChange: (value: iTwoStepDropdownData) => void;
  error?: FormFieldError;
}

export const OpsSelect2Step = (props: Props) => {
  const { label, options, value, error } = props;
  const [optionsRight, setOptionsRight] = useState<SelectOption[]>([]);
  const [selectedLeft, setSelectedLeft] = useState<SelectOption | null>(
    value.parent ? options.filter((option) => option.name === value.parent)?.[0] : null
  );

  const [selectedRight, setSelectedRight] = useState<SelectOption | null>(
    value.child ? optionsRight.filter((option) => option.id === value.child)?.[0] : null
  );

  useEffect(() => {
    setSelectedRight(
      value.child ? optionsRight.filter((option) => option.id === value.child)?.[0] : null
    );
  }, [value.child, optionsRight]);

  useEffect(() => {
    if (value) {
      props.onChange(value);
    }
  }, []);

  const setRightDropdownOptions = useCallback(async () => {
    const objectName = selectedLeft?.id;

    if (!objectName) {
      return;
    }

    const queryString = getDropdownOptionsForRelatedPeers({
      peers: [objectName],
    });

    const query = gql`
      ${queryString}
    `;

    const { data } = await graphqlClient.query({
      query,
    });

    const options = data[objectName];

    setOptionsRight(
      options.map((option: any) => ({
        name: option.display_label,
        id: option.id,
      }))
    );
  }, [selectedLeft?.id]);

  useEffect(() => {
    setRightDropdownOptions();
  }, [selectedLeft, setRightDropdownOptions]);

  return (
    <div className={classNames("grid grid-cols-6")}>
      <div className="sm:col-span-6">
        <label className="block text-sm font-medium leading-6 text-gray-900 capitalize">
          {label}
        </label>
      </div>
      <div className="sm:col-span-3 mr-2 mt-1">
        <OpsSelect
          error={error}
          disabled={false}
          value={selectedLeft ? selectedLeft.id : value.parent}
          options={options.map((o) => ({
            name: o.name,
            id: o.id,
          }))}
          label=""
          onChange={(e) => {
            setSelectedLeft(options.filter((option) => option.id === e.id)[0]);
            // setSelectedRight(null);
          }}
        />
      </div>
      <div className="sm:col-span-3 ml-2 mt-1">
        {!!selectedLeft && optionsRight.length > 0 && (
          <OpsSelect
            error={error}
            disabled={false}
            value={selectedRight ? selectedRight.id : value.child}
            options={optionsRight.map((o) => ({
              name: o.name,
              id: o.id,
            }))}
            label=""
            onChange={(e) => {
              const newOption = optionsRight.filter((option) => option.id === e.id)?.[0];
              setSelectedRight(newOption);
              props.onChange({
                parent: selectedLeft.id,
                child: e.id,
              });
            }}
          />
        )}
      </div>
    </div>
  );
};

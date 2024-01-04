import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { getDropdownOptionsForRelatedPeersPaginated } from "../../graphql/queries/objects/dropdownOptionsForRelatedPeers";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { classNames } from "../../utils/common";
import { SelectOption } from "../inputs/select";
import { OpsSelect } from "./select";

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

  const [optionsRight, setOptionsRight] = useState<SelectOption[]>([]);

  const [selectedLeft, setSelectedLeft] = useState<SelectOption | null | undefined>(
    value.parent ? options.find((option: SelectOption) => option.id === value.parent) : null
  );

  const [selectedRight, setSelectedRight] = useState<SelectOption | null | undefined>(
    value.child ? optionsRight.find((option) => option.id === value.child) : null
  );

  useEffect(() => {
    setSelectedRight(value.child ? optionsRight.find((option) => option.id === value.child) : null);
  }, [value.child, optionsRight]);

  useEffect(() => {
    setSelectedLeft(value.parent ? options.find((option) => option.id === value.parent) : null);
  }, [value.parent]);

  useEffect(() => {
    if (value) {
      onChange(value);
    }
  }, []);

  const setRightDropdownOptions = useCallback(async () => {
    const objectName = selectedLeft?.id;

    if (!objectName) {
      return;
    }

    const queryString = getDropdownOptionsForRelatedPeersPaginated({
      peers: [objectName],
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

    const newRigthOptions = data[objectName]?.edges.map((edge: any) => edge.node);

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
      setSelectedRight(newRigthOptions.find((option: any) => option.id === value.child));
    }
  }, [selectedLeft?.id]);

  useEffect(() => {
    setRightDropdownOptions();
  }, [selectedLeft?.id]);

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
          value={selectedLeft?.id}
          options={options}
          label=""
          onChange={(value) => {
            setSelectedLeft(options.filter((option) => option.id === value.id)[0]);
          }}
          isProtected={isProtected}
          data-cy="select2step-1"
        />
      </div>
      <div className="sm:col-span-3 ml-2 mt-1">
        {!!selectedLeft?.id && optionsRight.length > 0 && (
          <OpsSelect
            error={error}
            disabled={false}
            value={selectedRight?.id}
            options={optionsRight}
            label=""
            onChange={(value) => {
              const newOption = optionsRight.find((option) => option.id === value.id);
              setSelectedRight(newOption);
              onChange({
                parent: selectedLeft.id,
                child: value.id,
              });
            }}
            isProtected={isProtected}
            data-cy="select2step-2"
          />
        )}
      </div>
    </div>
  );
};

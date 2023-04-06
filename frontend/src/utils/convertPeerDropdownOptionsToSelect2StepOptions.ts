import * as R from "ramda";
import { iTwoStepSelectOption } from "../components/select-2-step";
import { iSchemaKindNameMap } from "../state/atoms/schemaKindName.atom";
import { iPeerDropdownOptions } from "./dropdownOptionsForRelatedPeers";

export const convertPeerDropdownOptionsToSelect2StepOptions = (
  options: iPeerDropdownOptions,
  schemaKindNameMap: iSchemaKindNameMap
): iTwoStepSelectOption[] => {
  return R.toPairs(options).map((option) => ({
    label: schemaKindNameMap[option[0]],
    value: option[0],
    options: option[1].map((item) => ({
      label: item.display_label,
      value: item.id,
    })),
  }));
};

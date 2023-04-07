import * as R from "ramda";
import { SelectOption } from "../screens/edit-form-hook/dynamic-control-types";
import { iSchemaKindNameMap } from "../state/atoms/schemaKindName.atom";
import { iPeerDropdownOptions } from "./dropdownOptionsForRelatedPeers";

export const convertPeerDropdownOptionsToSelect2StepOptions = (
  options: iPeerDropdownOptions,
  schemaKindNameMap: iSchemaKindNameMap
): SelectOption[] => {
  return R.toPairs(options).map((option) => ({
    label: schemaKindNameMap[option[0]],
    value: option[0],
    options: [
      { label: "", value: "" },
      ...option[1].map((item) => ({
        label: item.display_label,
        value: item.id,
      })),
    ],
  }));
};

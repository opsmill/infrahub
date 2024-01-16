import * as R from "ramda";
import { SelectOption } from "../components/inputs/select";
import { iSchemaKindNameMap } from "../state/atoms/schemaKindName.atom";
import { iPeerDropdownOptions } from "./dropdownOptionsForRelatedPeers";

export const convertPeerDropdownOptionsToSelect2StepOptions = (
  options: iPeerDropdownOptions,
  schemaKindNameMap: iSchemaKindNameMap
): SelectOption[] => {
  return R.toPairs(options).map((option) => ({
    name: schemaKindNameMap[option[0]],
    id: option[0],
    options: [
      {
        name: "",
        id: "",
      },
      ...option[1].map((item) => ({
        name: item.display_label,
        id: item.id,
      })),
    ],
  }));
};

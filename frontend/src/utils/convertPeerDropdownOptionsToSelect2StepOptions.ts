import * as R from "ramda";
import { iSchemaKindNameMap } from "../state/atoms/schemaKindName.atom";
import { iPeerDropdownOptions } from "./dropdownOptionsForRelatedPeers";
import { SelectOption } from "../components/select";

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
        id: ""
      },
      ...option[1]
      .map(
        (item) => ({
          name: item.display_label,
          id: item.id,
        })
      ),
    ],
  }));
};

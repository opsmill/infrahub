import { DynamicFieldData } from "../screens/edit-form-hook/dynamic-control-types";
import { iComboBoxFilter } from "../state/atoms/filters.atom";

const getFormStructureForFilters = (
  schema: any,
  currentFilters: any,
  peerDropdownOptions: any
): DynamicFieldData[] => {
  return schema.filters
    ?.map((filter: any) => {
      const currentValue = currentFilters?.find((f: iComboBoxFilter) => f.name === filter.name);

      if (filter.kind === "Number") {
        return {
          label: filter.name,
          name: filter.name,
          type: "number",
          value: currentValue ?? "",
        };
      }

      if (filter.kind === "Text" && !filter.enum) {
        return {
          label: filter.name,
          name: filter.name,
          type: "text",
          value: currentValue ?? "",
        };
      }

      if (filter.kind === "Text" && filter.enum) {
        return {
          label: filter.name,
          name: filter.name,
          type: "select",
          value: currentValue ?? "",
          options: filter.enum?.map((row: any) => ({
            name: row,
            id: row,
          })),
        };
      }

      if (filter.kind === "Object") {
        if (filter.object_kind && peerDropdownOptions && peerDropdownOptions[filter.object_kind]) {
          const { edges } = peerDropdownOptions[filter.object_kind];

          const options = edges.map((row: any) => ({
            name: row.node.display_label,
            id: row.node.id,
          }));

          return {
            label: filter.name,
            name: filter.name,
            type: "select",
            value: currentValue ? currentValue.value : "",
            options,
          };
        }
      }

      return null;
    })
    .filter(Boolean);
};

export default getFormStructureForFilters;

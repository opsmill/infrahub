import { DynamicFieldData } from "../screens/edit-form-hook/dynamic-control-types";

export const getFormStructureForAddObjectToGroup = (groups: any[]): DynamicFieldData[] => {
  const options = groups.map((group) => ({
    id: group.id,
    name: group?.label?.value,
  }));

  return [
    {
      label: "Group",
      name: "groupids",
      value: "",
      type: "multiselect",
      options: {
        values: options,
      },
    },
  ];
};

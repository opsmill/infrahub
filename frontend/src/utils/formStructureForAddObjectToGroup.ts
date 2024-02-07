import { DynamicFieldData } from "../screens/edit-form-hook/dynamic-control-types";

export const getFormStructureForAddObjectToGroup = (
  groups: any[],
  objectGroups: any[]
): DynamicFieldData[] => {
  const options = groups.map((group) => ({
    id: group.id,
    name: group?.label?.value,
  }));

  const values = objectGroups?.map((group) => group.id);

  return [
    {
      label: "Group",
      name: "groupids",
      value: values,
      type: "multiselect",
      options,
    },
  ];
};

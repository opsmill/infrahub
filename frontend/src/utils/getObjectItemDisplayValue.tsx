import { CheckIcon, XMarkIcon } from "@heroicons/react/24/outline";

export const getObjectItemDisplayValue = (row: any, attribute: any) => {
  // Get "value" or "display_name" depending on the kind (attribute or relationship)
  const value = row[attribute?.name]?.value ?? row[attribute?.name]?.display_label ?? "-";

  if (row[attribute?.name]?.value === false) {
    return <XMarkIcon className="h-4 w-4" />;
  }

  if (row[attribute?.name]?.value === true) {
    return <CheckIcon className="h-4 w-4" />;
  }

  return value;
};

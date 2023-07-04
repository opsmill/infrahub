import { CheckIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { Badge } from "../components/badge";

export const getObjectItemDisplayValue = (row: any, attribute: any) => {
  if (!row) {
    return;
  }

  if (row[attribute?.name]?.value === false) {
    return <XMarkIcon className="h-4 w-4" />;
  }

  if (row[attribute?.name]?.value === true) {
    return <CheckIcon className="h-4 w-4" />;
  }

  if (row[attribute?.name]?.edges) {
    const items = row[attribute?.name]?.edges.map(
      (edge: any) => edge?.node?.display_label ?? edge?.node?.value ?? "-"
    );

    return (
      <div className="flex">
        {items.map((item: string, index: number) => (
          <Badge key={index}>{item}</Badge>
        ))}
      </div>
    );
  }

  return (
    row[attribute?.name]?.value ??
    row[attribute?.name]?.node?.value ??
    row[attribute?.name]?.display_label ??
    row[attribute?.name]?.node?.display_label ??
    row[attribute?.name] ??
    "-"
  );
};

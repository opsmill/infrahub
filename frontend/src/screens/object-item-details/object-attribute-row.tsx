import { ReactElement } from "react";

type AttributeRowProps = {
  name: string;
  value: string | ReactElement;
};
export const ObjectAttributeRow = ({ name, value }: AttributeRowProps) => {
  return (
    <div className="p-2 grid grid-cols-3 gap-4 text-xs">
      <dt className="font-medium text-gray-500 flex items-center h-8">{name}</dt>
      <dd className="flex items-center gap-2">{value}</dd>
    </div>
  );
};

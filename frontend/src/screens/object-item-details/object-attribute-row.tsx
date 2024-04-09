import { ReactElement } from "react";
import { CopyToClipboard } from "../../components/buttons/copy-to-clipboard";

type ObjectAttributeRowProps = {
  name: string;
  value: string | ReactElement;
  enableCopyToClipboard?: boolean;
};
export const ObjectAttributeRow = ({
  name,
  value,
  enableCopyToClipboard,
}: ObjectAttributeRowProps) => {
  return (
    <div className="p-2 grid grid-cols-3 gap-4 text-xs">
      <dt className="font-medium text-gray-500 flex items-center h-8">{name}</dt>
      <dd className="flex items-center gap-2">
        {value}
        {enableCopyToClipboard && <CopyToClipboard text={value.toString()} />}
      </dd>
    </div>
  );
};

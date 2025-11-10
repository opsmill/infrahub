import type { ReactElement } from "react";

import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";

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
    <div className="grid grid-cols-[200px_auto] gap-4 px-4 py-2 text-xs">
      <dt className="flex h-8 items-center font-medium text-gray-500">{name}</dt>
      <dd className="flex items-center gap-2">
        {value}
        {enableCopyToClipboard && (
          <CopyToClipboard className="text-gray-500" text={value.toString()} />
        )}
      </dd>
    </div>
  );
};

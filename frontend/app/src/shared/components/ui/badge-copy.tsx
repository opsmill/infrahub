import type { ReactNode } from "react";

import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";

interface BadgeCopyProps {
  value: string;
  children?: ReactNode;
}

export function BadgeCopy({ value, children }: BadgeCopyProps) {
  return (
    <div className="flex items-center overflow-hidden rounded-md border border-gray-200 bg-white p-0 font-normal">
      <div className="px-2">{children || value}</div>

      <CopyToClipboard text={value} className="rounded-none bg-gray-200" />
    </div>
  );
}

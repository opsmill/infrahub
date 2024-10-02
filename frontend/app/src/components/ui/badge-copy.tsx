import { ReactNode } from "react";
import { CopyToClipboard } from "../buttons/copy-to-clipboard";

interface BadgeCopyProps {
  value: string;
  children?: ReactNode;
}

export function BadgeCopy({ value, children }: BadgeCopyProps) {
  return (
    <div className="flex items-center font-normal rounded-md bg-white border border-gray-200 p-0 overflow-hidden">
      <div className="px-2">{children || value}</div>

      <CopyToClipboard text={value} className="bg-gray-200 rounded-none" />
    </div>
  );
}

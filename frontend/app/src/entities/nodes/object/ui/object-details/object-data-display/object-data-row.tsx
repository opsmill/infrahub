import type React from "react";

import { classNames } from "@/shared/utils/common";

interface ObjectDataRowProps {
  name: React.ReactNode;
  value: React.ReactNode;
  className?: string;
}

export function ObjectDataRow({ name, value, className }: ObjectDataRowProps) {
  return (
    <div className={classNames("grid grid-cols-[200px_auto] gap-4 px-4 py-2 text-xs", className)}>
      <dt className="flex h-8 items-center font-medium text-gray-500">{name}</dt>
      <dd className="flex items-center gap-2 overflow-hidden">{value}</dd>
    </div>
  );
}

import type React from "react";

interface ObjectDataRowProps {
  name: React.ReactNode;
  value: React.ReactNode;
}

export function ObjectDataRow({ name, value }: ObjectDataRowProps) {
  return (
    <div className="grid grid-cols-[200px_auto] gap-4 px-4 py-2 text-xs">
      <dt className="flex h-8 items-center font-medium text-gray-500">{name}</dt>
      <dd className="flex items-center gap-2">{value}</dd>
    </div>
  );
}

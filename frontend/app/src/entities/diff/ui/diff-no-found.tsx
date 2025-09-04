import { Icon } from "@iconify-icon/react";

import { DiffBadge } from "@/entities/diff/node-diff/utils";

export interface DiffNoFoundProps {
  diffStatus: string;
}

export function DiffNoFound({ diffStatus }: DiffNoFoundProps) {
  return (
    <div className="flex flex-col items-center mt-10 gap-5">
      <div className="p-3 rounded-full bg-white inline-flex">
        <Icon icon="mdi:circle-off-outline" className="text-2xl text-custom-blue-800" />
      </div>

      <div className="text-center">
        <h1 className="font-semibold">
          No matches found for the status <DiffBadge status={diffStatus} />
        </h1>
        <p>Try adjusting the filter settings to include more results.</p>
      </div>
    </div>
  );
}

import { Icon } from "@iconify-icon/react";

import { DiffBadge } from "@/entities/diff/ui/node-diff/utils";

export interface DiffNoFoundProps {
  diffStatus: string;
}

export function DiffNoFound({ diffStatus }: DiffNoFoundProps) {
  return (
    <div className="mt-10 flex flex-col items-center gap-5">
      <div className="inline-flex rounded-full bg-white p-3">
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

import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";

import type { CoreDataCheck } from "@/shared/api/graphql/generated/graphql";
import { Badge } from "@/shared/components/ui/badge";

import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";

import { DataConflict } from "./data-conflict";

export const DataIntegrityConflicts = ({ conflicts }: Pick<CoreDataCheck, "conflicts">) => {
  const proposedChangesDetails = useAtomValue(proposedChangedState);

  return (
    <div className="rounded-md border border-gray-100 bg-white p-2">
      <div className="grid grid-cols-3">
        <Badge variant="green" className="col-start-2 col-end-3 bg-transparent">
          <Icon icon="mdi:layers-triple" className="mr-1" />{" "}
          {proposedChangesDetails.destination_branch?.value}
        </Badge>

        <Badge variant="blue" className="bg-transparent">
          <Icon icon="mdi:layers-triple" className="mr-1" />{" "}
          {proposedChangesDetails.source_branch?.value}
        </Badge>
      </div>

      <div>
        {conflicts?.value?.map((conflict: any) => {
          return <DataConflict key={conflict.id} {...conflict} />;
        })}
      </div>
    </div>
  );
};

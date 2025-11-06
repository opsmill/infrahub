import { Icon } from "@iconify-icon/react";

import { HomeCard } from "@/shared/components/ui/home-card";
import { classNames } from "@/shared/utils/common";

import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import { ProposedChangesTable } from "@/entities/proposed-changes/ui/proposed-changes-table";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface ProposedChangesProps {
  className?: string;
}

export const ProposedChanges = ({ className }: ProposedChangesProps) => {
  const { schema: proposedChangeSchema } = useSchema(PROPOSED_CHANGE_OBJECT);

  return (
    <HomeCard className={classNames("", className)}>
      <HomeCard.Title className="flex items-center gap-2">
        <Icon icon={"mdi:file-replace-outline"} className={"text-base"} /> Open Proposed changes
      </HomeCard.Title>

      <RequireObjectPermissions objectKind={PROPOSED_CHANGE_OBJECT}>
        {({ permission }) => {
          return (
            <ObjectTableProvider schema={proposedChangeSchema}>
              <ProposedChangesTable
                permission={permission}
                schema={proposedChangeSchema}
                hideFilters
              />
            </ObjectTableProvider>
          );
        }}
      </RequireObjectPermissions>
    </HomeCard>
  );
};

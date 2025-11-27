import { Icon } from "@iconify-icon/react";

import { constructPath } from "@/shared/api/rest/fetch";
import { HomeCard } from "@/shared/components/ui/home-card";
import { classNames } from "@/shared/utils/common";

import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import { ProposedChangesTableHomepage } from "@/entities/proposed-changes/ui/proposed-changes-table-homepage";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface ProposedChangesWidgetProps {
  className?: string;
}

export const ProposedChangesWidget = ({ className }: ProposedChangesWidgetProps) => {
  const { schema: proposedChangeSchema } = useSchema(PROPOSED_CHANGE_OBJECT);

  return (
    <HomeCard className={classNames("flex flex-col", className)}>
      <HomeCard.Title className="flex items-center justify-between">
        <span className="flex items-center gap-2">
          <Icon icon={"mdi:file-replace-outline"} /> Open Proposed changes
        </span>

        <HomeCard.Link to={constructPath("/proposed-changes")}>
          View all <Icon icon={"mdi:chevron-right"} />
        </HomeCard.Link>
      </HomeCard.Title>

      <ObjectTableProvider schema={proposedChangeSchema!}>
        <ProposedChangesTableHomepage
          schema={proposedChangeSchema}
          className="m-0 rounded-none border-none"
        />
      </ObjectTableProvider>
    </HomeCard>
  );
};

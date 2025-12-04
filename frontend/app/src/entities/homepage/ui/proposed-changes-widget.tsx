import { Icon } from "@iconify-icon/react";

import { constructPath } from "@/shared/api/rest/fetch";
import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { HomeCard } from "@/shared/components/ui/home-card";

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
    <HomeCard className={className}>
      <HomeCard.Title>
        <Row>
          <Icon icon={"mdi:file-replace-outline"} /> Open Proposed changes
        </Row>

        <HomeCard.Link to={constructPath("/proposed-changes")}>
          View all <Icon icon={"mdi:chevron-right"} />
        </HomeCard.Link>
      </HomeCard.Title>

      {proposedChangeSchema ? (
        <ObjectTableProvider schema={proposedChangeSchema}>
          <ProposedChangesTableHomepage schema={proposedChangeSchema} />
        </ObjectTableProvider>
      ) : (
        <ErrorScreen message={`${PROPOSED_CHANGE_OBJECT} schema not found`} />
      )}
    </HomeCard>
  );
};

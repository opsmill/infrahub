import Content from "@/shared/components/layout/content";
import { useTitle } from "@/shared/hooks/useTitle";

import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/utils/constant";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ProposedChangesManager } from "./proposed-changes-manager";

export const ProposedChangesPage = () => {
  useTitle("Proposed changes");
  const { schema: proposedChangeSchema } = useSchema(PROPOSED_CHANGE_OBJECT);

  if (!proposedChangeSchema) {
    return <ErrorScreen message={`Schema ${PROPOSED_CHANGE_OBJECT} not found.`} />;
  }

  return (
    <Content.Card>
      <ProposedChangesManager schema={proposedChangeSchema} />
    </Content.Card>
  );
};

import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import { ProposedChangesManager } from "@/entities/proposed-changes/ui/proposed-changes-manager";
import { NodeSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { useTitle } from "@/shared/hooks/useTitle";

export const Component = () => {
  useTitle("Proposed changes");
  const { schema: proposedChangeSchema } = useSchema(PROPOSED_CHANGE_OBJECT);

  if (!proposedChangeSchema) {
    return <ErrorScreen message={`Schema ${PROPOSED_CHANGE_OBJECT} not found.`} />;
  }

  return (
    <Content.Card>
      <ProposedChangesManager schema={proposedChangeSchema as NodeSchema} />
    </Content.Card>
  );
};

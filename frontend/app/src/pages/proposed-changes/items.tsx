import Content from "@/shared/components/layout/content";
import { useTitle } from "@/shared/hooks/useTitle";

import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import { ProposedChangesManager } from "@/entities/proposed-changes/ui/proposed-changes-manager";
import type { NodeSchema } from "@/entities/schema/types";
import { useCoreSchema } from "@/entities/schema/ui/hooks/useCoreSchema";

export const Component = () => {
  useTitle("Proposed changes");
  const { schema: proposedChangeSchema } = useCoreSchema(PROPOSED_CHANGE_OBJECT);

  return (
    <Content.Card className="flex flex-col">
      <ProposedChangesManager schema={proposedChangeSchema as NodeSchema} />
    </Content.Card>
  );
};

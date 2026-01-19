import Content from "@/shared/components/layout/content";
import { useTitle } from "@/shared/hooks/useTitle";

import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import { ProposedChangesManager } from "@/entities/proposed-changes/ui/proposed-changes-manager";
import type { NodeSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export const Component = () => {
  useTitle("Proposed changes");
  const { schema: proposedChangeSchema } = useSchema(PROPOSED_CHANGE_OBJECT, { required: true });

  return (
    <Content.Card className="flex flex-col">
      <ProposedChangesManager schema={proposedChangeSchema as NodeSchema} />
    </Content.Card>
  );
};

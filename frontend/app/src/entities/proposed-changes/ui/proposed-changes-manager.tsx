import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import { ProposedChangesTable } from "@/entities/proposed-changes/ui/proposed-changes-table";
import type { NodeSchema } from "@/entities/schema/types";

import { ProposedChangesManagerToolbar } from "./proposed-changes-manager-toolbar";

export interface ProposedChangesManagerProps {
  schema: NodeSchema;
}

export function ProposedChangesManager({
  schema: proposedChangeSchema,
}: ProposedChangesManagerProps) {
  return (
    <RequireObjectPermissions objectKind={PROPOSED_CHANGE_OBJECT}>
      {({ permission }) => {
        return (
          <ObjectTableProvider schema={proposedChangeSchema}>
            <ProposedChangesManagerToolbar permission={permission} schema={proposedChangeSchema} />
            <ProposedChangesTable permission={permission} schema={proposedChangeSchema} />
          </ObjectTableProvider>
        );
      }}
    </RequireObjectPermissions>
  );
}

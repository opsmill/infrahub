import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
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
    <RequireObjectPermissions schema={proposedChangeSchema}>
      {({ permission }) => {
        return (
          <ObjectTableProvider schema={proposedChangeSchema}>
            <ProposedChangesManagerToolbar permission={permission} schema={proposedChangeSchema} />
            <ProposedChangesTable schema={proposedChangeSchema} />
          </ObjectTableProvider>
        );
      }}
    </RequireObjectPermissions>
  );
}

import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import {
  ProposedChangesTable,
  ProposedChangesTableProps,
} from "@/entities/proposed-changes/ui/proposed-changes-table";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/utils/constant";
import { ModelSchema } from "@/entities/schema/types";
import { ProposedChangesManagerToolbar } from "./proposed-changes-manager-toolbar";

export interface ProposedChangesManagerProps {
  schema: ModelSchema;
  baseFilters?: ProposedChangesTableProps["baseFilters"];
}

export function ProposedChangesManager({
  schema: proposedChangeSchema,
  baseFilters,
}: ProposedChangesManagerProps) {
  return (
    <RequireObjectPermissions objectKind={PROPOSED_CHANGE_OBJECT}>
      {({ permission }) => {
        return (
          <>
            <ProposedChangesManagerToolbar permission={permission} schema={proposedChangeSchema} />
            <ProposedChangesTable
              permission={permission}
              schema={proposedChangeSchema}
              baseFilters={baseFilters}
            />
          </>
        );
      }}
    </RequireObjectPermissions>
  );
}

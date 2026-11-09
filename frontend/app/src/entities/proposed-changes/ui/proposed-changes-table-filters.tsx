import { useQueryState } from "nuqs";

import { QSP } from "@/shared/config/qsp";

import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import { TableColumnHeader } from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { CLOSE_STATE } from "@/entities/proposed-changes/domain/model/proposed-change-state";
import { ProposedChangeTableFilterLink } from "@/entities/proposed-changes/ui/proposed-change-table-filter-link";
import { useGetProposedChangesCounts } from "@/entities/proposed-changes/ui/queries/get-proposed-changes-counts.query";
import type { NodeSchema } from "@/entities/schema/domain/model/schema";

interface ProposedChangesTableHeaderProps {
  schema: NodeSchema;
}

export function ProposedChangesTableFilters({ schema }: ProposedChangesTableHeaderProps) {
  const [proposedChangeState, setProposedChangeState] = useQueryState(QSP.PROPOSED_CHANGES_STATE);
  const [filters] = useFilters();

  const { data } = useGetProposedChangesCounts({ filters });

  const draftAttribute = schema.attributes?.find((attribute) => {
    return attribute.name === "is_draft";
  });

  const stateAttribute = schema.attributes?.find((attribute) => {
    return attribute.name === "state";
  });

  const sourceBranchAttribute = schema.attributes?.find((attribute) => {
    return attribute.name === "source_branch";
  });

  const reviewersRelationship = schema.relationships?.find((relationship) => {
    return relationship.name === "reviewers";
  });

  const approversRelationship = schema.relationships?.find((relationship) => {
    return relationship.name === "approved_by";
  });

  return (
    <div className="flex items-center justify-between gap-2 p-3 pt-0">
      <div className="flex items-center">
        <ProposedChangeTableFilterLink
          isActive={!proposedChangeState}
          onClick={() => {
            setProposedChangeState(null);
          }}
        >
          Opened {data?.opened ? `(${data.opened})` : null}
        </ProposedChangeTableFilterLink>

        <ProposedChangeTableFilterLink
          isActive={proposedChangeState === CLOSE_STATE}
          onClick={() => {
            setProposedChangeState(CLOSE_STATE);
          }}
        >
          Closed {data?.closed ? `(${data.closed})` : null}
        </ProposedChangeTableFilterLink>
      </div>
      <div className="flex items-center">
        {draftAttribute && (
          <TableColumnHeader
            schema={schema}
            columnSchema={draftAttribute}
            className="rounded-sm border-0 transition-all"
          />
        )}

        {stateAttribute && (
          <TableColumnHeader
            schema={schema}
            columnSchema={stateAttribute}
            className="rounded-sm border-0 transition-all"
          />
        )}

        {sourceBranchAttribute && (
          <TableColumnHeader
            schema={schema}
            columnSchema={sourceBranchAttribute}
            className="rounded-sm border-0 transition-all"
          />
        )}

        {reviewersRelationship && (
          <TableColumnHeader
            schema={schema}
            columnSchema={reviewersRelationship}
            className="rounded-sm border-0 transition-all"
          />
        )}

        {approversRelationship && (
          <TableColumnHeader
            schema={schema}
            columnSchema={approversRelationship}
            className="rounded-sm border-0 transition-all"
          />
        )}
      </div>
    </div>
  );
}

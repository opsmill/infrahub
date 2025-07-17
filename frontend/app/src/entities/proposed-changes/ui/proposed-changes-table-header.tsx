import { QSP } from "@/config/qsp";
import { QSP_STATE_CLOSE_VALUE } from "@/entities/proposed-changes/constant";
import { useProposedChangesCounts } from "@/entities/proposed-changes/domain/get-proposed-changes-counts.query";
import { TableFilter } from "@/entities/proposed-changes/ui/table-column-header";
import { TableFilterLink } from "@/entities/proposed-changes/ui/table-column-header-link";
import { NodeSchema } from "@/entities/schema/types";
import useFilters from "@/shared/hooks/useFilters";
import { StringParam, useQueryParam } from "use-query-params";

interface ProposedChangesTableHeaderProps {
  schema: NodeSchema;
}

export function ProposedChangesTableHeader({ schema }: ProposedChangesTableHeaderProps) {
  const [proposedChangeState, setProposedChangeState] = useQueryParam(
    QSP.PROPOSED_CHANGES_STATE,
    StringParam
  );
  const [filters] = useFilters();

  const { data } = useProposedChangesCounts({ filters });

  const stateAttribute = schema.attributes?.find((attribute) => {
    return attribute.name === "state";
  });

  const sourceBranchAttribute = schema.attributes?.find((attribute) => {
    return attribute.name === "source_branch";
  });

  const authorRelationship = schema.relationships?.find((relationship) => {
    return relationship.name === "created_by";
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
        <TableFilterLink
          isActive={!proposedChangeState}
          onClick={() => {
            setProposedChangeState(undefined);
          }}
        >
          Opened ({data?.opened})
        </TableFilterLink>
        <TableFilterLink
          isActive={proposedChangeState === QSP_STATE_CLOSE_VALUE}
          onClick={() => {
            setProposedChangeState(QSP_STATE_CLOSE_VALUE);
          }}
        >
          Closed ({data?.closed})
        </TableFilterLink>
      </div>

      <div className="flex items-center">
        {stateAttribute && <TableFilter schema={schema} columnSchema={stateAttribute} />}
        {sourceBranchAttribute && (
          <TableFilter schema={schema} columnSchema={sourceBranchAttribute} />
        )}
        {authorRelationship && <TableFilter schema={schema} columnSchema={authorRelationship} />}
        {reviewersRelationship && (
          <TableFilter schema={schema} columnSchema={reviewersRelationship} />
        )}
        {approversRelationship && (
          <TableFilter schema={schema} columnSchema={approversRelationship} />
        )}
      </div>
    </div>
  );
}

import { QSP } from "@/config/qsp";
import { QSP_STATE_CLOSE_VALUE } from "@/entities/proposed-changes/constant";
import { useGetProposedChangesCounts } from "@/entities/proposed-changes/domain/get-proposed-changes-counts.query";
import { ProposedChangeTableFilter } from "@/entities/proposed-changes/ui/proposed-change-table-filter";
import { ProposedChangeTableFilterLink } from "@/entities/proposed-changes/ui/proposed-change-table-filter-link";
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

  const { data } = useGetProposedChangesCounts({ filters });

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
        <ProposedChangeTableFilterLink
          isActive={!proposedChangeState}
          onClick={() => {
            setProposedChangeState(undefined);
          }}
        >
          Opened {data?.opened ? `(${data.opened})` : null}
        </ProposedChangeTableFilterLink>
        <ProposedChangeTableFilterLink
          isActive={proposedChangeState === QSP_STATE_CLOSE_VALUE}
          onClick={() => {
            setProposedChangeState(QSP_STATE_CLOSE_VALUE);
          }}
        >
          Closed {data?.closed ? `(${data.closed})` : null}
        </ProposedChangeTableFilterLink>
      </div>

      <div className="flex items-center">
        {stateAttribute && (
          <ProposedChangeTableFilter schema={schema} columnSchema={stateAttribute} />
        )}
        {sourceBranchAttribute && (
          <ProposedChangeTableFilter schema={schema} columnSchema={sourceBranchAttribute} />
        )}
        {authorRelationship && (
          <ProposedChangeTableFilter schema={schema} columnSchema={authorRelationship} />
        )}
        {reviewersRelationship && (
          <ProposedChangeTableFilter schema={schema} columnSchema={reviewersRelationship} />
        )}
        {approversRelationship && (
          <ProposedChangeTableFilter schema={schema} columnSchema={approversRelationship} />
        )}
      </div>
    </div>
  );
}

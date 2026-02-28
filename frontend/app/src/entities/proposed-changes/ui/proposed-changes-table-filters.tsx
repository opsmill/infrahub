import { useQueryState } from "nuqs";

import { QSP } from "@/shared/config/qsp";
import useFilters from "@/shared/hooks/useFilters";

import { CLOSE_STATE } from "@/entities/proposed-changes/constants";
import { ProposedChangeTableFilter } from "@/entities/proposed-changes/ui/proposed-change-table-filter";
import { ProposedChangeTableFilterLink } from "@/entities/proposed-changes/ui/proposed-change-table-filter-link";
import { useGetProposedChangesCounts } from "@/entities/proposed-changes/ui/queries/get-proposed-changes-counts.query";
import type { NodeSchema } from "@/entities/schema/types";

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
          <ProposedChangeTableFilter schema={schema} columnSchema={draftAttribute} />
        )}

        {stateAttribute && (
          <ProposedChangeTableFilter schema={schema} columnSchema={stateAttribute} />
        )}

        {sourceBranchAttribute && (
          <ProposedChangeTableFilter schema={schema} columnSchema={sourceBranchAttribute} />
        )}

        {authorRelationship && (
          <ProposedChangeTableFilter
            schema={schema}
            columnSchema={authorRelationship}
            customLabel={"Author"}
          />
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

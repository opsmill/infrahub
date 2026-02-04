import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import { TableCell } from "@/shared/components/table/table-cell";
import { LinkButton } from "@/shared/components/ui/button";
import { QSP } from "@/shared/config/qsp";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import { useGetProposedChanges } from "@/entities/proposed-changes/domain/get-proposed-changes.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

interface BranchProposedChangesCellProps {
  branchName: string;
}

export function BranchProposedChangesCell({ branchName }: BranchProposedChangesCellProps) {
  // Use required schema - guaranteed to exist for Core namespace objects
  const { schema } = useSchema(PROPOSED_CHANGE_OBJECT, { throwIfNotFound: true });

  // Query proposed changes for this specific branch
  const { data: proposedChangesData } = useGetProposedChanges({
    schema,
    filters: [{ name: "source_branch__value", value: branchName }],
  });

  // Get all proposed changes from all pages
  const proposedChanges = proposedChangesData?.pages?.flat() ?? [];
  const firstPC = proposedChanges[0]?.items?.[0];

  // Show empty state if no proposed changes
  if (!firstPC) {
    return (
      <TableCell className="h-auto min-h-14">
        <span className="text-gray-400">-</span>
      </TableCell>
    );
  }

  const remainingCount = proposedChanges.length - 1;

  // URL for first proposed change detail
  const detailUrl = getObjectDetailsUrl(PROPOSED_CHANGE_OBJECT, firstPC.id);

  // URL for filtered list (if more than one)
  const listUrl = getObjectDetailsUrl(PROPOSED_CHANGE_OBJECT, undefined, [
    {
      name: QSP.FILTER,
      value: JSON.stringify([{ name: "source_branch__value", value: branchName }]),
    },
  ]);

  return (
    <TableCell className="h-auto min-h-14">
      <div className="flex flex-wrap items-center gap-2">
        <LinkButton
          variant="outline"
          size="sm"
          to={detailUrl}
          className="max-w-40 rounded-full pr-2.5 hover:border-custom-blue-700 hover:underline"
        >
          <Icon icon={getSchemaIcon(schema)} className="mr-1 shrink-0 text-custom-blue-800" />
          <span className="truncate">{firstPC.node.name.value}</span>
        </LinkButton>

        {remainingCount > 0 && (
          <Link
            to={listUrl}
            className="shrink-0 whitespace-nowrap text-gray-500 text-sm hover:underline"
          >
            +{remainingCount} more
          </Link>
        )}
      </div>
    </TableCell>
  );
}

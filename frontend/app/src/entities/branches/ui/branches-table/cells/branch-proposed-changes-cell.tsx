import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import { Row } from "@/shared/components/container";
import { TableCell } from "@/shared/components/table/table-cell";
import { LinkButton } from "@/shared/components/ui/button";
import { Spinner } from "@/shared/components/ui/spinner";
import { QSP } from "@/shared/config/qsp";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import {
  OPEN_STATE,
  PROPOSED_CHANGE_OBJECT,
  STATE_VALUES_FILTER,
} from "@/entities/proposed-changes/constants";
import { useGetProposedChanges } from "@/entities/proposed-changes/domain/get-proposed-changes.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

const OPEN_STATE_FILTER = { name: STATE_VALUES_FILTER, value: [OPEN_STATE] };

interface BranchProposedChangesCellProps {
  branchName: string;
}

export function BranchProposedChangesCell({ branchName }: BranchProposedChangesCellProps) {
  const { schema } = useSchema(PROPOSED_CHANGE_OBJECT, { throwIfNotFound: true });
  const filters = [{ name: "source_branch__value", value: branchName }, OPEN_STATE_FILTER];
  const { data, isPending } = useGetProposedChanges({ schema, filters });

  if (isPending) {
    return (
      <TableCell className="h-auto min-h-14">
        <Spinner />
      </TableCell>
    );
  }

  const totalCount = data?.pages?.[0]?.count ?? 0;
  const firstPC = data?.pages?.[0]?.items?.[0];

  if (!firstPC) {
    return (
      <TableCell className="h-auto min-h-14">
        <span className="text-gray-400">-</span>
      </TableCell>
    );
  }

  const remainingCount = totalCount - 1;
  const detailUrl = getObjectDetailsUrl(PROPOSED_CHANGE_OBJECT, firstPC.id);
  const listUrl = getObjectDetailsUrl(PROPOSED_CHANGE_OBJECT, undefined, [
    { name: QSP.FILTER, value: JSON.stringify(filters) },
  ]);

  return (
    <TableCell className="h-auto min-h-14">
      <Row className="flex-wrap">
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
      </Row>
    </TableCell>
  );
}

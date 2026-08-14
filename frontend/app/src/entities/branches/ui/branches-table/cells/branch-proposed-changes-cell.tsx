import { LinkButton, Spinner } from "@infrahub/ui";
import { Link } from "react-router";

import { Row } from "@/shared/components/container";
import { Icon } from "@/shared/components/display/icon";
import { TableCell } from "@/shared/components/table/table-cell";
import { QSP } from "@/shared/config/qsp";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change";
import {
  OPEN_STATE,
  STATE_VALUES_FILTER,
} from "@/entities/proposed-changes/domain/model/proposed-change-state";
import { useGetProposedChanges } from "@/entities/proposed-changes/ui/queries/get-proposed-changes.query";
import { getSchemaIcon } from "@/entities/schema/domain/rules/get-schema-icon";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

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
        <span className="text-subtle-muted">-</span>
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
          href={detailUrl}
          className="max-w-40 rounded-full pr-2.5 data-hovered:border-custom-blue-700 data-hovered:underline"
        >
          <Icon icon={getSchemaIcon(schema)} className="shrink-0 text-custom-blue-800" />
          <span className="truncate">{firstPC.node.name.value}</span>
        </LinkButton>

        {remainingCount > 0 && (
          <Link
            to={listUrl}
            className="shrink-0 whitespace-nowrap text-foreground-muted text-sm hover:underline"
          >
            +{remainingCount} more
          </Link>
        )}
      </Row>
    </TableCell>
  );
}

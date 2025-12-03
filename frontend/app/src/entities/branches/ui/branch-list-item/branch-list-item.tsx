import { ListBoxItem, type ListBoxItemProps } from "react-aria-components";

import type { Branch } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { Col, Row } from "@/shared/components/container";
import { focusVisibleStyle } from "@/shared/components/style-rac";
import { classNames } from "@/shared/utils/common";
import { formatFullDate } from "@/shared/utils/date";

import { BranchDefaultBadge } from "@/entities/branches/ui/branch-list-item/branch-default-badge";
import { BranchGitSyncBadge } from "@/entities/branches/ui/branch-list-item/branch-git-sync-badge";
import { BranchMetadata } from "@/entities/branches/ui/branch-list-item/branch-metadata";
import { BranchSchemaChangesBadge } from "@/entities/branches/ui/branch-list-item/branch-schema-changes-badge";
import { BranchStatusBadge } from "@/entities/branches/ui/branch-list-item/branch-status-badge";

interface BranchListItemProps extends ListBoxItemProps {
  branch: Branch;
}

export function BranchListItem({ branch, className, ...props }: BranchListItemProps) {
  return (
    <ListBoxItem
      textValue={branch.name}
      href={constructPath(`/branches/${branch.name}`)}
      className={classNames(
        focusVisibleStyle,
        "flex flex-wrap items-center gap-6 px-6 py-4",
        "border border-transparent not-last:border-b-gray-200",
        "first:rounded-t-lg last:rounded-b-lg",
        "hover:bg-neutral-100",
        className
      )}
      {...props}
    >
      <Col className="min-w-1/3 flex-1 gap-0 text-sm">
        <Row className="shrink-0">
          <span className="font-semibold">{branch.name}</span>

          {branch.is_default ? (
            <BranchDefaultBadge />
          ) : (
            <BranchStatusBadge status={branch.status} />
          )}

          {branch.has_schema_changes && <BranchSchemaChangesBadge />}
        </Row>

        <p className="truncate text-gray-600 text-xs">{branch.description}</p>
      </Col>

      {branch.sync_with_git && <BranchGitSyncBadge />}

      <Row className="ml-auto gap-6">
        <BranchMetadata
          label="last rebase"
          value={branch.branched_from ? formatFullDate(branch.branched_from) : "-"}
        />
        <BranchMetadata
          label="created at"
          value={branch.created_at ? formatFullDate(branch.created_at) : "-"}
        />
      </Row>
    </ListBoxItem>
  );
}

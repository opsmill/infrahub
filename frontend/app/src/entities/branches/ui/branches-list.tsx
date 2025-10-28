import { ListBox, ListBoxItem, type ListBoxItemProps } from "react-aria-components";

import type { Branch } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { focusVisibleStyle } from "@/shared/components/style-rac";
import { useTitle } from "@/shared/hooks/useTitle";
import { classNames, sortByName } from "@/shared/utils/common";
import { formatFullDate } from "@/shared/utils/date";

import { useGetBranches } from "@/entities/branches/domain/get-branches.query";
import { BranchDefaultBadge } from "@/entities/branches/ui/branch-default-badge";
import { BranchGitSyncBadge } from "@/entities/branches/ui/branch-git-sync-badge";
import { BranchMetadata } from "@/entities/branches/ui/branch-metadata";
import { BranchSchemaChangesBadge } from "@/entities/branches/ui/branch-schema-changes-badge";
import { BranchStatusBadge } from "@/entities/branches/ui/branch-status-badge";

export default function BranchesList() {
  useTitle("Branches list");
  const { data: storedBranches, refetch, isPending, error, isRefetching } = useGetBranches();

  if (isPending) {
    return <InfrahubLoading>loading branches...</InfrahubLoading>;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const sortedBranches = sortByName(storedBranches.filter((b) => b.name !== "main"));
  const branches = [...storedBranches.filter((b) => b.name === "main"), ...sortedBranches];

  return (
    <Content.Card>
      <Content.CardTitle
        title="Branches"
        badgeContent={branches.length}
        isReloadLoading={isRefetching}
        reload={() => refetch()}
      />

      <ListBox
        aria-label="Branches list"
        items={branches}
        className="m-6 flex flex-col divide-y rounded-lg border border-gray-200"
      >
        {(branch) => <BranchListItem branch={branch} />}
      </ListBox>
    </Content.Card>
  );
}

interface BranchListItemProps extends ListBoxItemProps {
  branch: Branch;
}
function BranchListItem({ branch, className, ...props }: BranchListItemProps) {
  return (
    <ListBoxItem
      textValue={branch.name}
      href={constructPath(`/branches/${branch.name}`)}
      className={classNames(
        focusVisibleStyle,
        "flex flex-wrap items-center gap-6 p-5",
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

        <p className="truncate text-gray-600 text-sm">{branch.description}</p>
      </Col>

      <BranchGitSyncBadge isSyncWithGit={!!branch.sync_with_git} />

      <Row className="ml-auto gap-6">
        <BranchMetadata
          label="last rebase on"
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

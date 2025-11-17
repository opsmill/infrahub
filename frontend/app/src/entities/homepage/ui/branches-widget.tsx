import { Icon } from "@iconify-icon/react";
import { ListBox } from "react-aria-components";

import type { Branch } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { HomeCard } from "@/shared/components/ui/home-card";
import { classNames, sortByCreatedAtDesc } from "@/shared/utils/common";

import { useGetBranches } from "@/entities/branches/domain/get-branches.query";
import { BranchListItem } from "@/entities/branches/ui/branch-list-item/branch-list-item";

import { EmptyHomeCard } from "./empty-home-card";

interface BranchesWidgetProps {
  className?: string;
}

export const BranchesWidget = ({ className }: BranchesWidgetProps) => {
  const { data: storedBranches, isPending, error } = useGetBranches();

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const sortedBranches = sortByCreatedAtDesc(
    (storedBranches?.filter((b) => b.name !== "main" && b.created_at) ?? []) as (Branch & {
      created_at: string;
    })[]
  );
  const branches = [...(storedBranches?.filter((b) => b.name === "main") ?? []), ...sortedBranches];

  return (
    <HomeCard className={classNames("flex h-full flex-col", className)}>
      <HomeCard.Title className="flex items-center justify-between">
        <span className="flex items-center gap-2">
          <Icon icon={"mdi:source-branch"} /> Branches
        </span>

        <HomeCard.Link to={constructPath("/branches")}>
          View all <Icon icon={"mdi:chevron-right"} />
        </HomeCard.Link>
      </HomeCard.Title>

      {isPending && <LoadingIndicator />}

      {branches.length === 0 && (
        <EmptyHomeCard
          title={"You don’t have any open branches yet"}
          subtitle={"Create your first branch to start tracking changes."}
        />
      )}

      {!!branches.length && (
        <ListBox
          aria-label="Branches list"
          items={branches}
          className="flex h-full flex-col divide-y"
        >
          {(branch) => <BranchListItem branch={branch} />}
        </ListBox>
      )}
    </HomeCard>
  );
};

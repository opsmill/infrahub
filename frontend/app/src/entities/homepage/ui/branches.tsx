import { Icon } from "@iconify-icon/react";

import { ListBox } from "@/shared/components/aria/list-box";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { HomeCard } from "@/shared/components/ui/home-card";
import { sortByName } from "@/shared/utils/common";

import { useGetBranches } from "@/entities/branches/domain/get-branches.query";
import { BranchListItem } from "@/entities/branches/ui/branch-list-item/branch-list-item";

import { EmptyHomeCard } from "./empty-home-card";

export const Branches = () => {
  const { data: storedBranches, isPending, error } = useGetBranches();

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const sortedBranches = sortByName(storedBranches?.filter((b) => b.name !== "main") ?? []);
  const branches = [...(storedBranches?.filter((b) => b.name === "main") ?? []), ...sortedBranches];
  // const branches = [];

  return (
    <HomeCard className="flex h-full min-h-40 flex-col">
      <HomeCard.Title className="flex items-center justify-between">
        <span className="flex items-center gap-2">
          <Icon icon={"mdi:source-branch"} /> Branches
        </span>

        <HomeCard.Link to={"/branches"}>
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
          className="flex h-full flex-col divide-y overflow-scroll"
        >
          {(branch) => <BranchListItem branch={branch} />}
        </ListBox>
      )}
    </HomeCard>
  );
};

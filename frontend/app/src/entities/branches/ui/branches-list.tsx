import { ListBox } from "react-aria-components";

import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { useTitle } from "@/shared/hooks/useTitle";
import { sortByName } from "@/shared/utils/common";

import { useGetBranches } from "@/entities/branches/domain/get-branches.query";
import { BranchListItem } from "@/entities/branches/ui/branch-list-item/branch-list-item";

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
        className="m-2 flex flex-col divide-y rounded-lg border border-gray-200 dark:divide-slate-600 dark:border-slate-600"
      >
        {(branch) => <BranchListItem branch={branch} />}
      </ListBox>
    </Content.Card>
  );
}

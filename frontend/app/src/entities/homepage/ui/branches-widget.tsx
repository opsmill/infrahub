import { Icon } from "@iconify-icon/react";
import { ListBox } from "react-aria-components";
import * as R from "remeda";

import { constructPath } from "@/shared/api/rest/fetch";
import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ScrollArea } from "@/shared/components/ui/scroll-area";

import { BranchListItem } from "@/entities/branches/ui/branch-list-item/branch-list-item";
import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import { HomeCard } from "@/entities/homepage/ui/home-card";

import { EmptyHomeCard } from "./empty-home-card";

interface BranchesWidgetProps {
  className?: string;
}

export const BranchesWidget = ({ className }: BranchesWidgetProps) => {
  return (
    <HomeCard className={className}>
      <HomeCard.Title>
        <Row>
          <Icon icon={"mdi:source-branch"} /> Branches
        </Row>

        <HomeCard.Link to={constructPath("/branches")}>
          View all <Icon icon={"mdi:chevron-right"} />
        </HomeCard.Link>
      </HomeCard.Title>

      <BranchesWidgetContent />
    </HomeCard>
  );
};

function BranchesWidgetContent() {
  const { data, isPending, error } = useGetBranches();

  if (isPending) {
    return <LoadingIndicator />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (data.length === 0) {
    return (
      <EmptyHomeCard
        title={"You don't have any open branches yet"}
        subtitle={"Create your first branch to start tracking changes."}
      />
    );
  }

  const [defaultBranches, otherBranches] = R.partition(data, (branch) => !!branch?.is_default);
  const sortedBranches = R.sortBy(otherBranches, [(x) => x.created_at ?? 0, "desc"]);
  const branches = [...defaultBranches, ...sortedBranches];

  return (
    <ScrollArea>
      <ListBox
        aria-label="Branches list"
        items={branches}
        className="flex h-full flex-col divide-y"
      >
        {(branch) => <BranchListItem branch={branch} />}
      </ListBox>
    </ScrollArea>
  );
}

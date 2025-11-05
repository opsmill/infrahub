import { Icon } from "@iconify-icon/react";

import { GENERIC_REPOSITORY_KIND } from "@/config/constants";

import { HomeCard } from "@/shared/components/ui/home-card";

export const GitRepositories = () => {
  return (
    <HomeCard>
      <HomeCard.Title className="flex items-center justify-between">
        Git repositories{" "}
        <HomeCard.Link to={`/objects/${GENERIC_REPOSITORY_KIND}`}>
          View all <Icon icon={"mdi:chevron-right"} />
        </HomeCard.Link>{" "}
      </HomeCard.Title>
      OK
    </HomeCard>
  );
};

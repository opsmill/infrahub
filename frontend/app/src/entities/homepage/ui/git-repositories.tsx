import { Icon } from "@iconify-icon/react";
import React from "react";
import { ListBox } from "react-aria-components";

import { GENERIC_REPOSITORY_KIND } from "@/config/constants";

import type { CoreRepository } from "@/shared/api/graphql/generated/graphql";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { HomeCard } from "@/shared/components/ui/home-card";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import { classNames } from "@/shared/utils/common";

import { useObjects } from "@/entities/nodes/object/domain/get-objects.query";
import { REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME } from "@/entities/repository/constants";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { EmptyHomeCard } from "./empty-home-card";
import { GitRepositoryItem } from "./git-repository";

interface GitRepositoriesProps {
  className?: string;
}

export const GitRepositories = ({ className }: GitRepositoriesProps) => {
  const { schema } = useSchema(GENERIC_REPOSITORY_KIND);

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } = useObjects({
    schema: schema!,
    getAttributesVisible: (attributes) => {
      return attributes.filter(({ name }) => {
        return name === REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME;
      });
    },
    getRelationshipsVisible: () => [],
  });

  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  const isLoading = isPending || isFetchingNextPage;

  return (
    <HomeCard className={classNames("flex flex-col", className)}>
      <HomeCard.Title className="flex items-center justify-between">
        <span className="flex items-center gap-2">
          <Icon icon={"mdi:git"} /> Git repositories
        </span>

        <HomeCard.Link to={`/objects/${GENERIC_REPOSITORY_KIND}`}>
          View all <Icon icon={"mdi:chevron-right"} />
        </HomeCard.Link>
      </HomeCard.Title>

      <InfiniteScroll hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
        <ListBox
          aria-label="Git repositories list"
          items={flatData}
          renderEmptyState={() => (
            <EmptyHomeCard
              title={"No git repository connected"}
              subtitle={"Connect a Git repo to sync changes."}
              className="py-10"
            />
          )}
        >
          {(repository) => {
            return (
              <GitRepositoryItem
                {...(repository as unknown as CoreRepository)}
                key={repository.id}
              />
            );
          }}
        </ListBox>

        {isLoading && <LoadingIndicator />}
      </InfiniteScroll>
    </HomeCard>
  );
};

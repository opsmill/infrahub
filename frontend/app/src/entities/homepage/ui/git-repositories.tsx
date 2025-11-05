import { Icon } from "@iconify-icon/react";
import React from "react";

import { GENERIC_REPOSITORY_KIND } from "@/config/constants";

import type { CoreRepository } from "@/shared/api/graphql/generated/graphql";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { HomeCard } from "@/shared/components/ui/home-card";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";

import { useObjects } from "@/entities/nodes/object/domain/get-objects.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { EmptyHomeCard } from "./empty-home-card";
import { GitRepositoryItem } from "./git-repository";

export const GitRepositories = () => {
  const { schema } = useSchema(GENERIC_REPOSITORY_KIND);

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } = useObjects({
    schema: schema!,
  });

  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  const isLoading = isPending || isFetchingNextPage;

  return (
    <HomeCard className="flex h-full flex-col">
      <HomeCard.Title className="flex items-center justify-between">
        Git repositories
        <HomeCard.Link to={`/objects/${GENERIC_REPOSITORY_KIND}`}>
          View all <Icon icon={"mdi:chevron-right"} />
        </HomeCard.Link>
      </HomeCard.Title>
      <InfiniteScroll
        scrollX
        hasNextPage={hasNextPage}
        onLoadMore={fetchNextPage}
        className="flex flex-col gap-2"
      >
        {flatData.length === 0 && (
          <EmptyHomeCard
            title={"No git repository connected"}
            subtitle={"Connect a Git repo to sync changes."}
          />
        )}

        {flatData.map((repository) => {
          return (
            <GitRepositoryItem {...(repository as unknown as CoreRepository)} key={repository.id} />
          );
        })}

        {isLoading && <LoadingIndicator />}
      </InfiniteScroll>
    </HomeCard>
  );
};

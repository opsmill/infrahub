import { Icon } from "@iconify-icon/react";
import { Collection, ListBox, ListBoxLoadMoreItem } from "react-aria-components";

import type { CoreRepository } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { HomeCard } from "@/shared/components/ui/home-card";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { GENERIC_REPOSITORY_KIND } from "@/shared/config/constants";

import { EmptyHomeCard } from "@/entities/homepage/ui/empty-home-card";
import { GitRepositoryItem } from "@/entities/homepage/ui/git-repository";
import { useObjects } from "@/entities/nodes/object/domain/get-objects.query";
import { REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME } from "@/entities/repository/constants";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface GitRepositoriesWidgetProps {
  className?: string;
}

export function GitRepositoriesWidget({ className }: GitRepositoriesWidgetProps) {
  return (
    <HomeCard className={className}>
      <HomeCard.Title>
        <Row>
          <Icon icon={"mdi:git"} /> Git repositories
        </Row>

        <HomeCard.Link to={constructPath(`/objects/${GENERIC_REPOSITORY_KIND}`)}>
          View all <Icon icon={"mdi:chevron-right"} />
        </HomeCard.Link>
      </HomeCard.Title>

      <GitRepositoriesWidgetContent />
    </HomeCard>
  );
}

export function GitRepositoriesWidgetContent() {
  const { schema } = useSchema(GENERIC_REPOSITORY_KIND);

  const { data, error, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } = useObjects({
    schema: schema!,
    getAttributesVisible: (attributes) => {
      return attributes.filter(({ name }) => {
        return name === REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME;
      });
    },
    getRelationshipsVisible: () => [],
  });

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const flatData = data?.pages?.flat() ?? [];

  if (flatData.length === 0) {
    return (
      <EmptyHomeCard
        title="No git repository connected"
        subtitle="Connect a Git repo to sync changes."
      />
    );
  }

  return (
    <ScrollArea>
      <ListBox aria-label="Git repositories list">
        <Collection items={flatData}>
          {(repository) => <GitRepositoryItem {...(repository as unknown as CoreRepository)} />}
        </Collection>

        {hasNextPage && (
          <ListBoxLoadMoreItem isLoading={isFetchingNextPage} onLoadMore={fetchNextPage}>
            <LoadingIndicator />
          </ListBoxLoadMoreItem>
        )}
      </ListBox>
    </ScrollArea>
  );
}

import { Button } from "@infrahub/ui";
import { type ReactNode, useId } from "react";

import { Col, Row } from "@/shared/components/container";
import { Icon } from "@/shared/components/display/icon";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { classNames } from "@/shared/utils/common";
import { getOffset } from "@/shared/utils/table-pagination";

import type { ObjectResult } from "@/entities/navigation/domain/use-cases/search-anywhere";
import {
  SEARCH_RESULTS_PAGE_SIZE,
  useGetSearchResultsPage,
} from "@/entities/navigation/ui/queries/search-anywhere.query";
import { SearchResultLink } from "@/entities/navigation/ui/search-results/search-result-link";
import { SearchResultsPager } from "@/entities/navigation/ui/search-results/search-results-pager";

interface SearchResultsListProps {
  search: string;
  caseSensitive: boolean;
  page: number;
  onPageChange: (page: number) => void;
}

export function SearchResultsList({
  search,
  caseSensitive,
  page,
  onPageChange,
}: SearchResultsListProps) {
  const { data, error, isPending, isPlaceholderData, refetch } = useGetSearchResultsPage({
    search,
    caseSensitive,
    page,
  });

  if (search === "") {
    return (
      <NoDataFound
        title="No search text"
        message="Type a text in the search box to list the matching objects."
        icon={<Icon icon="mdi:magnify" className="mb-2 text-3xl" />}
      />
    );
  }

  if (isPending) return <LoadingIndicator className="p-8" />;

  if (error) {
    return (
      <div role="alert">
        <ErrorScreen
          message={
            <Col className="items-center gap-2">
              Could not load the search results.
              <Button variant="outline" size="xs" onPress={() => refetch()}>
                Try again
              </Button>
            </Col>
          }
        />
      </div>
    );
  }

  const { matchingObjects, parentPrefixes, hasMore } = data;

  if (matchingObjects.length === 0 && page > 1) {
    return (
      <Row role="status" className="p-4 text-sm">
        Page {page} has no results.
        <Button variant="outline" size="xs" className="ml-auto" onPress={() => onPageChange(1)}>
          Go to first page
        </Button>
      </Row>
    );
  }

  return (
    <Col className="items-stretch gap-4 p-4">
      {parentPrefixes && (
        <SearchResultsSection
          title="Parent prefixes"
          nodes={parentPrefixes}
          emptyMessage="No containing prefixes found."
        />
      )}

      <SearchResultsSection
        title="Objects"
        nodes={matchingObjects}
        emptyMessage={`No objects match "${search}".`}
        isLoading={isPlaceholderData}
      >
        <SearchResultsPager
          page={page}
          offset={getOffset(page, SEARCH_RESULTS_PAGE_SIZE)}
          rowCount={matchingObjects.length}
          hasMore={hasMore}
          onPageChange={onPageChange}
        />
      </SearchResultsSection>
    </Col>
  );
}

interface SearchResultsSectionProps {
  title: string;
  nodes: ObjectResult[];
  emptyMessage: string;
  isLoading?: boolean;
  children?: ReactNode;
}

function SearchResultsSection({
  title,
  nodes,
  emptyMessage,
  isLoading = false,
  children,
}: SearchResultsSectionProps) {
  const headingId = useId();

  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-1 rounded-xl border bg-input p-2 shadow-card"
    >
      <h2 id={headingId} className="px-2 py-1.5 font-medium text-subtle text-xs">
        {title}
      </h2>

      {nodes.length === 0 ? (
        <p className="px-2 pb-1.5 text-foreground-muted text-sm">{emptyMessage}</p>
      ) : (
        <ul aria-busy={isLoading} className={classNames(isLoading && "opacity-60")}>
          {nodes.map((node) => (
            <SearchResultLink key={node.id} node={node} />
          ))}
        </ul>
      )}

      {children}
    </section>
  );
}

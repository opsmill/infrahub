import { Button, Card, CardHeader } from "@infrahub/ui";
import React from "react";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { TablePagination } from "@/shared/components/table/table-pagination";
import { Badge } from "@/shared/components/ui/badge";
import { formatNumberDisplay } from "@/shared/utils/number";
import { getTotalPages } from "@/shared/utils/table-pagination";

interface PagedQuery<TPage> {
  data: TPage | undefined;
  error: Error | null;
  isPlaceholderData: boolean;
  refetch: () => unknown;
}

export interface PagedTableCardProps<TPage extends { count: number }> {
  title: string;
  /** What the rows are, read by screen readers after the count and in the loading label. */
  itemName: { one: string; other: string };
  query: PagedQuery<TPage>;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  headerActions?: React.ReactNode;
  isDenied?: (error: Error) => boolean;
  deniedMessage?: string;
  failedMessage: string;
  emptyTitle: string;
  emptyMessage: React.ReactNode;
  renderTable: (page: TPage) => React.ReactNode;
  tableTestId: string;
  /** Shown under the body once the list has rows. */
  footer?: React.ReactNode;
  "data-testid"?: string;
}

export function PagedTableCard<TPage extends { count: number }>({
  headerActions,
  footer,
  "data-testid": testId,
  ...bodyProps
}: PagedTableCardProps<TPage>) {
  const { title, itemName, query } = bodyProps;
  const titleId = React.useId();
  const count = query.data?.count;

  return (
    <Card role="region" aria-labelledby={titleId} className="overflow-hidden" data-testid={testId}>
      <CardHeader className="flex items-center gap-2">
        <h2 id={titleId}>{title}</h2>
        {count !== undefined && (
          <Badge variant="blue" className="rounded-full font-normal tabular-nums">
            {formatNumberDisplay(count)}{" "}
            <span className="sr-only">{count === 1 ? itemName.one : itemName.other}</span>
          </Badge>
        )}
        {headerActions}
      </CardHeader>

      <PagedTableBody {...bodyProps} />

      {!!count && footer}
    </Card>
  );
}

type PagedTableBodyProps<TPage extends { count: number }> = Omit<
  PagedTableCardProps<TPage>,
  "headerActions" | "footer" | "data-testid"
>;

function PagedTableBody<TPage extends { count: number }>({
  title,
  itemName,
  query: { data, error, isPlaceholderData, refetch },
  page,
  pageSize,
  onPageChange,
  isDenied,
  deniedMessage,
  failedMessage,
  emptyTitle,
  emptyMessage,
  renderTable,
  tableTestId,
}: PagedTableBodyProps<TPage>) {
  if (!data && !error) return <PagedTableLoading label={`Loading ${itemName.other}`} />;

  if (!data) {
    if (error && isDenied?.(error)) {
      return <UnauthorizedScreen className="flex-none p-6" defaultOpen message={deniedMessage} />;
    }

    // A failed page past the first has no pager to leave it, as the count came with the page.
    return (
      <PagedTableFailed
        message={failedMessage}
        action={
          page > 1
            ? { label: "Go to first page", onPress: () => onPageChange(1) }
            : { label: "Try again", onPress: () => refetch() }
        }
      />
    );
  }

  if (data.count === 0) return <NoDataFound title={emptyTitle} message={emptyMessage} />;

  const lastPage = getTotalPages(data.count, pageSize);
  // Placeholder rows carry the previous page's count, which can't tell whether this page exists.
  if (page > lastPage && !isPlaceholderData) {
    return <PagedTablePageOutOfRange page={page} onGoToLastPage={() => onPageChange(lastPage)} />;
  }

  const hasMultiplePages = data.count > pageSize;

  return (
    <>
      <div
        // The header and a full page of h-10 rows, so a short last page doesn't move what is below.
        className={hasMultiplePages ? "min-h-110 overflow-x-auto" : "overflow-x-auto"}
        data-testid={tableTestId}
      >
        {renderTable(data)}
      </div>

      {hasMultiplePages && (
        <TablePagination
          className="border-t"
          aria-label={`${title} pagination`}
          page={page}
          pageSize={pageSize}
          totalCount={data.count}
          onPageChange={onPageChange}
        />
      )}
    </>
  );
}

function PagedTableLoading({ label }: { label: string }) {
  return (
    <div role="status" aria-busy="true">
      <span className="sr-only">{label}</span>
      {[0, 1, 2].map((index) => (
        <Row key={index} className="h-10 gap-4 border-b px-3 last:border-b-0">
          <Skeleton className="h-3 w-2/5" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-3 w-16" />
        </Row>
      ))}
    </div>
  );
}

interface PagedTableFailedProps {
  message: string;
  action: { label: string; onPress: () => void };
}

function PagedTableFailed({ message, action }: PagedTableFailedProps) {
  return (
    <div role="alert">
      <ErrorScreen
        className="flex-none gap-2 p-6 text-sm"
        message={
          <Col className="items-center">
            {message}
            <Button variant="outline" size="xs" onPress={action.onPress}>
              {action.label}
            </Button>
          </Col>
        }
      />
    </div>
  );
}

interface PagedTablePageOutOfRangeProps {
  page: number;
  onGoToLastPage: () => void;
}

function PagedTablePageOutOfRange({ page, onGoToLastPage }: PagedTablePageOutOfRangeProps) {
  return (
    <Row role="status" className="px-4 py-4 text-sm">
      Page {page} doesn't exist.
      <Button variant="outline" size="xs" className="ml-auto" onPress={onGoToLastPage}>
        Go to last page
      </Button>
    </Row>
  );
}

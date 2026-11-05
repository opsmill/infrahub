import { Spinner } from "@infrahub/ui";
import {
  Row as AriaRow,
  Cell,
  Collection,
  Column,
  Table,
  TableBody,
  TableHeader,
  TableLayout,
  TableLoadMoreItem,
  Virtualizer,
} from "react-aria-components";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { Link } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";
import { formatNumberDisplay } from "@/shared/utils/number";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { IpPoolResource } from "@/entities/resource-manager/domain/model/ip-pool";
import { IP_ADDRESS_POOL, type IpPoolKind } from "@/entities/resource-manager/domain/model/pool";
import { KindLabel } from "@/entities/resource-manager/ui/pool/kind-label";
import { PoolLoadMoreError } from "@/entities/resource-manager/ui/pool/pool-load-more-error";
import { useGetIpPoolAllocations } from "@/entities/resource-manager/ui/queries/get-ip-pool-allocations.query";

const ROW_HEIGHT = 36;
const HEADING_HEIGHT = 32;
const LOADER_HEIGHT = 44;
const SKELETON_WIDTHS = ["w-40", "w-56", "w-32", "w-48", "w-64", "w-36", "w-52", "w-44"];

const focusRing =
  "outline-none data-focus-visible:ring-2 data-focus-visible:ring-ring-halo data-focus-visible:ring-inset";
const columnStyle = classNames(
  "flex h-full items-center px-3 text-left font-medium text-foreground-muted text-xs",
  focusRing
);
const cellStyle = classNames("flex h-full min-w-0 items-center px-3 text-sm", focusRing);
const plainLinkStyle = "no-underline decoration-solid underline-offset-2 hover:underline";

function SkeletonRows() {
  return (
    <div role="status" aria-busy="true" aria-label="Loading allocations">
      {SKELETON_WIDTHS.map((width) => (
        <Row key={width} className="gap-0 border-border/50 border-b" style={{ height: ROW_HEIGHT }}>
          <div className="w-40 px-3">
            <Skeleton className="h-3 w-28" />
          </div>
          <div className="px-3">
            <Skeleton className={classNames("h-3", width)} />
          </div>
        </Row>
      ))}
    </div>
  );
}

export interface IpPoolAllocationsTableProps {
  poolId: string;
  poolKind: IpPoolKind;
  resource: IpPoolResource;
}

export function IpPoolAllocationsTable({
  poolId,
  poolKind,
  resource,
}: IpPoolAllocationsTableProps) {
  const {
    data,
    error,
    isPending,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
  } = useGetIpPoolAllocations({ poolId, resourceId: resource.id });

  if (error && !data) return <ErrorScreen message={error.message} />;

  // a failed page must not be cancelled and restarted by the next scroll or retry
  const loadNextPage = () => fetchNextPage({ cancelRefetch: false });

  const allocations = data?.pages.flatMap((page) => page.allocations) ?? [];
  const count = data?.pages[0]?.count;
  const isAddressPool = poolKind === IP_ADDRESS_POOL;
  const noun = isAddressPool ? "addresses" : "prefixes";
  const title = `Allocated ${noun}`;

  return (
    <Col className="min-h-0 min-w-0 flex-1 gap-0">
      <Row className="border-b px-3 py-2">
        <h2 className="font-semibold text-sm">{title}</h2>
        {count !== undefined && (
          <span className="text-foreground-muted text-sm tabular-nums">
            {formatNumberDisplay(count)}
          </span>
        )}
        <span className="min-w-0 truncate text-foreground-muted text-sm">
          in{" "}
          <Link
            to={getObjectDetailsUrl(resource.__typename, resource.id)}
            className={classNames("text-foreground tabular-nums", plainLinkStyle)}
            title={`Open ${resource.display_label}`}
          >
            {resource.display_label}
          </Link>
        </span>
      </Row>

      <Virtualizer
        layout={TableLayout}
        layoutOptions={{
          rowHeight: ROW_HEIGHT,
          headingHeight: HEADING_HEIGHT,
          loaderHeight: LOADER_HEIGHT,
        }}
      >
        <Table
          aria-label={title}
          className={classNames(
            "relative min-h-0 w-full flex-1 overflow-y-auto overflow-x-hidden overscroll-contain bg-table-cell",
            // the card sizes to its rows, so an empty body needs its own height to show the message
            allocations.length === 0 && "min-h-52"
          )}
          style={{ scrollPaddingTop: HEADING_HEIGHT }}
        >
          {/* the virtualized header group has no height of its own, so without h-full its blur covers nothing */}
          <TableHeader className="h-full border-border/50 border-b backdrop-blur-sm">
            <Column isRowHeader width="2fr" minWidth={160} className={columnStyle}>
              {isAddressPool ? "Address" : "Prefix"}
            </Column>
            <Column width="3fr" minWidth={200} className={columnStyle}>
              Identifier
            </Column>
            <Column width="1fr" minWidth={120} className={columnStyle}>
              Kind
            </Column>
          </TableHeader>

          <TableBody
            renderEmptyState={() =>
              isPending ? (
                <SkeletonRows />
              ) : (
                <Row className="h-24 justify-center text-foreground-muted text-sm">
                  No {noun} in {resource.display_label} yet
                </Row>
              )
            }
          >
            <Collection items={allocations}>
              {(allocation) => (
                <AriaRow
                  id={allocation.id}
                  // the virtualizer leaves rows 1px tall and sets data-hovered only on rows with an action
                  className={classNames(
                    "h-full border-border/50 border-b transition-colors duration-100 hover:bg-content-muted data-focus-visible:bg-content-muted",
                    focusRing
                  )}
                >
                  <Cell className={cellStyle}>
                    <Link
                      to={getObjectDetailsUrl(allocation.__typename, allocation.id)}
                      className={classNames(
                        "truncate font-medium text-foreground tabular-nums",
                        plainLinkStyle
                      )}
                      title={allocation.display_label}
                    >
                      {allocation.display_label}
                    </Link>
                  </Cell>
                  <Cell className={cellStyle}>
                    {allocation.identifier === null ? (
                      <span className="text-foreground-muted">None</span>
                    ) : (
                      <span className="truncate font-mono text-xs" title={allocation.identifier}>
                        {allocation.identifier}
                      </span>
                    )}
                  </Cell>
                  <Cell className={classNames(cellStyle, "text-foreground-muted")}>
                    <KindLabel kind={allocation.__typename} />
                  </Cell>
                </AriaRow>
              )}
            </Collection>
            {hasNextPage && !isFetchNextPageError && (
              <TableLoadMoreItem
                onLoadMore={loadNextPage}
                isLoading={isFetchingNextPage}
                className="flex items-center justify-center gap-2 text-foreground-muted text-xs"
              >
                <Spinner className="size-3.5" /> Loading more
              </TableLoadMoreItem>
            )}
          </TableBody>
        </Table>
      </Virtualizer>
      {isFetchNextPageError && (
        <PoolLoadMoreError
          itemsLabel={noun}
          isRetrying={isFetchingNextPage}
          onRetry={loadNextPage}
        />
      )}
    </Col>
  );
}

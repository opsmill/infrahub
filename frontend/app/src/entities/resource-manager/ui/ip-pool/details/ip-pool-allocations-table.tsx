import {
  Table,
  TableBody,
  TableCell,
  TableColumn,
  TableEmptyMessage,
  TableHeader,
  TableLink,
  TableLoadMoreItem,
  TableRow,
  TableSkeleton,
} from "@infrahub/ui";
import React from "react";
import { Collection } from "react-aria-components";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { Link } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";
import { formatNumberDisplay } from "@/shared/utils/number";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { IpPoolResource } from "@/entities/resource-manager/domain/model/ip-pool";
import { IP_ADDRESS_POOL, type IpPoolKind } from "@/entities/resource-manager/domain/model/pool";
import { KindLabel } from "@/entities/resource-manager/ui/pool/kind-label";
import { PoolAllocationsError } from "@/entities/resource-manager/ui/pool/pool-allocations-error";
import { useGetIpPoolAllocations } from "@/entities/resource-manager/ui/queries/get-ip-pool-allocations.query";

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
  const titleId = React.useId();
  const {
    data,
    error,
    isPending,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
    isRefetchError,
    isRefetching,
    refetch,
  } = useGetIpPoolAllocations({ poolId, resourceId: resource.id });

  if (error && !data) return <ErrorScreen message={error.message} />;

  // a failed page must not be cancelled and restarted by the next scroll or retry
  const loadNextPage = () => fetchNextPage({ cancelRefetch: false });

  const allocations = data?.pages.flatMap((page) => page.allocations) ?? [];
  const count = data?.pages[0]?.count;
  const isAddressPool = poolKind === IP_ADDRESS_POOL;
  const noun = isAddressPool ? "addresses" : "prefixes";
  const title = `Allocated ${noun}`;
  const emptyMessage = `No ${noun} in ${resource.display_label} yet`;

  return (
    <Col className="min-h-0 min-w-0 flex-1 gap-0">
      <Row className="border-b px-3 py-2">
        <h2 id={titleId} className="font-semibold text-sm">
          {title}
        </h2>
        {count !== undefined && (
          <span className="text-foreground-muted text-sm tabular-nums">
            {formatNumberDisplay(count)}
          </span>
        )}
        <span className="min-w-0 truncate text-foreground-muted text-sm">
          in{" "}
          <Link
            to={getObjectDetailsUrl(resource.__typename, resource.id)}
            className={classNames(
              "text-foreground tabular-nums",
              "no-underline decoration-solid underline-offset-4 hover:underline"
            )}
            title={`Open ${resource.display_label}`}
          >
            {resource.display_label}
          </Link>
        </span>
      </Row>

      <Table aria-labelledby={titleId}>
        <TableHeader>
          <TableColumn isRowHeader>{isAddressPool ? "Address" : "Prefix"}</TableColumn>
          <TableColumn width="2fr">Identifier</TableColumn>
          <TableColumn>Kind</TableColumn>
          <TableColumn>ID</TableColumn>
        </TableHeader>

        <TableBody
          renderEmptyState={() =>
            isPending ? <TableSkeleton /> : <TableEmptyMessage>{emptyMessage}</TableEmptyMessage>
          }
        >
          <Collection items={allocations}>
            {(allocation) => (
              <TableRow id={allocation.id}>
                <TableCell textValue={allocation.display_label}>
                  <TableLink href={getObjectDetailsUrl(allocation.__typename, allocation.id)}>
                    {allocation.display_label}
                  </TableLink>
                </TableCell>
                <TableCell>{allocation.identifier ?? "-"}</TableCell>
                <TableCell>
                  <KindLabel kind={allocation.__typename} />
                </TableCell>
                <TableCell>{allocation.id}</TableCell>
              </TableRow>
            )}
          </Collection>
          {hasNextPage && !isFetchNextPageError && (
            <TableLoadMoreItem onLoadMore={loadNextPage} isLoading={isFetchingNextPage} />
          )}
        </TableBody>
      </Table>
      {isFetchNextPageError && (
        <PoolAllocationsError
          message={`More ${noun} could not be loaded.`}
          isRetrying={isFetchingNextPage}
          onRetry={loadNextPage}
        />
      )}
      {isRefetchError && (
        <PoolAllocationsError
          message={`The ${noun} could not be refreshed.`}
          isRetrying={isRefetching}
          onRetry={() => refetch()}
        />
      )}
    </Col>
  );
}

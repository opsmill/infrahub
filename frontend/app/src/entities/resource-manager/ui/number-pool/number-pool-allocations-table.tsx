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
import { QSP } from "@/shared/config/qsp";
import { classNames } from "@/shared/utils/common";
import { formatNumberDisplay } from "@/shared/utils/number";

import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import { getBranchDetailsUrl } from "@/entities/branches/ui/routing/branch-urls";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { NumberPoolRange } from "@/entities/resource-manager/domain/model/number-pool";
import {
  NUMBER_POOL_PROVENANCE_PROVIDED,
  type NumberPoolAllocation,
  type NumberPoolProvenance,
} from "@/entities/resource-manager/domain/model/number-pool";
import { useGetNumberPoolAllocationCount } from "@/entities/resource-manager/ui/queries/get-number-pool-allocation-count.query";
import { useGetNumberPoolAllocations } from "@/entities/resource-manager/ui/queries/get-number-pool-allocations.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

const ROW_HEIGHT = 36;
const HEADING_HEIGHT = 32;
const LOADER_HEIGHT = 44;
const NUMBER_WIDTH = 108;
const SKELETON_WIDTHS = ["w-40", "w-56", "w-32", "w-48", "w-64", "w-36", "w-52", "w-44"];

const focusRing =
  "outline-none data-focus-visible:ring-2 data-focus-visible:ring-ring-halo data-focus-visible:ring-inset";
const columnStyle = classNames(
  "flex h-full items-center px-3 text-left font-medium text-foreground-muted text-xs",
  focusRing
);
const cellStyle = classNames("flex h-full min-w-0 items-center px-3 text-sm", focusRing);
const plainLinkStyle = "no-underline decoration-solid underline-offset-2 hover:underline";

const allocationKey = ({ value, branch, holder }: NumberPoolAllocation) =>
  `${value}:${branch}:${holder.id}`;

// pool values are identifiers such as ASNs and VLAN IDs, which are written without separators
const formatSpan = ({ start, end }: Pick<NumberPoolRange, "start" | "end">) =>
  `${start.value} – ${end.value}`;

interface SourceTagProps {
  provenance: NumberPoolProvenance;
}

function SourceTag({ provenance }: SourceTagProps) {
  const isProvided = provenance === NUMBER_POOL_PROVENANCE_PROVIDED;

  return (
    <span
      className={classNames(
        "inline-flex h-5 items-center rounded-md border px-1.5 font-medium text-xs",
        isProvided ? "border-active/40 text-active" : "border-border-strong text-foreground-muted"
      )}
    >
      {isProvided ? "Provided" : "Allocated"}
    </span>
  );
}

interface KindLabelProps {
  kind: string;
}

function KindLabel({ kind }: KindLabelProps) {
  const { schema } = useSchema(kind);
  const label = schema?.label ?? kind;

  return (
    <span className="truncate" title={label}>
      {label}
    </span>
  );
}

function SkeletonRows() {
  return (
    <div role="status" aria-busy="true" aria-label="Loading allocations">
      {SKELETON_WIDTHS.map((width) => (
        <Row key={width} className="gap-0 border-border/50 border-b" style={{ height: ROW_HEIGHT }}>
          <div className="px-3" style={{ width: NUMBER_WIDTH }}>
            <Skeleton className="h-3 w-12" />
          </div>
          <div className="px-3">
            <Skeleton className={classNames("h-3", width)} />
          </div>
        </Row>
      ))}
    </div>
  );
}

export interface NumberPoolAllocationsTableProps {
  poolId: string;
  nodeKind: string;
  nodeAttribute: string;
  ranges: NumberPoolRange[];
  selectedRange: NumberPoolRange | null;
}

export function NumberPoolAllocationsTable({
  poolId,
  nodeKind,
  nodeAttribute,
  ranges,
  selectedRange,
}: NumberPoolAllocationsTableProps) {
  const { data, error, isPending, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useGetNumberPoolAllocations({ poolId, rangeId: selectedRange?.id });
  const { data: count } = useGetNumberPoolAllocationCount({ poolId, rangeId: selectedRange?.id });
  const { data: branches } = useGetBranches();
  const { schema: nodeSchema } = useSchema(nodeKind);

  if (error) return <ErrorScreen message={error.message} />;

  const defaultBranchName = branches?.find((branch) => branch.is_default)?.name;
  const allocations = data?.pages.flat() ?? [];
  const showRangeColumn = selectedRange === null && ranges.length > 1;
  const rangeById = new Map(ranges.map((range) => [range.id, range]));
  const numberHeader =
    nodeSchema?.attributes?.find(({ name }) => name === nodeAttribute)?.label ?? "Number";
  const objectHeader = nodeSchema?.label ?? "Object";
  const emptyMessage = selectedRange
    ? `No allocations in ${formatSpan(selectedRange)}`
    : "No allocations yet";

  return (
    <Col className="min-h-0 min-w-0 flex-1 gap-0">
      <Row className="border-b px-3 py-2">
        <h2 className="font-semibold text-sm">Allocations</h2>
        {count !== undefined && (
          <span className="text-foreground-muted text-sm tabular-nums">
            {formatNumberDisplay(count)}
          </span>
        )}
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
          aria-label="Allocations"
          className={classNames(
            "relative min-h-0 w-full flex-1 overflow-y-auto overflow-x-hidden overscroll-contain bg-table-cell",
            // the card sizes to its rows, so an empty body needs its own height to show the message
            allocations.length === 0 && "min-h-52"
          )}
          style={{ scrollPaddingTop: HEADING_HEIGHT }}
        >
          {/* the virtualized header group has no height of its own, so without h-full its blur covers nothing */}
          <TableHeader className="h-full border-border/50 border-b backdrop-blur-sm">
            <Column isRowHeader width={NUMBER_WIDTH} className={columnStyle}>
              {numberHeader}
            </Column>
            <Column width="2.5fr" minWidth={160} className={columnStyle}>
              {objectHeader}
            </Column>
            <Column width="1fr" minWidth={120} className={columnStyle}>
              Kind
            </Column>
            <Column width="1fr" minWidth={110} className={columnStyle}>
              Branch
            </Column>
            {showRangeColumn && (
              <Column width={150} className={columnStyle}>
                Range
              </Column>
            )}
            <Column width={104} className={columnStyle}>
              Source
            </Column>
          </TableHeader>

          <TableBody
            renderEmptyState={() =>
              isPending ? (
                <SkeletonRows />
              ) : (
                <Row className="h-24 justify-center text-foreground-muted text-sm">
                  {emptyMessage}
                </Row>
              )
            }
          >
            <Collection items={allocations} dependencies={[showRangeColumn, defaultBranchName]}>
              {(allocation) => {
                const isDefaultBranch = allocation.branch === defaultBranchName;
                const range = rangeById.get(allocation.rangeId);
                const holderLabel = allocation.holder.display_label ?? allocation.holder.id;

                return (
                  <AriaRow
                    id={allocationKey(allocation)}
                    // the virtualizer leaves rows 1px tall and sets data-hovered only on rows with an action
                    className={classNames(
                      "h-full border-border/50 border-b transition-colors duration-100 hover:bg-content-muted data-focus-visible:bg-content-muted",
                      focusRing
                    )}
                  >
                    <Cell className={classNames(cellStyle, "font-medium tabular-nums")}>
                      {allocation.value}
                    </Cell>
                    <Cell className={cellStyle}>
                      <Link
                        to={getObjectDetailsUrl(
                          allocation.holder.__typename,
                          allocation.holder.id,
                          [
                            isDefaultBranch
                              ? { name: QSP.BRANCH, exclude: true }
                              : { name: QSP.BRANCH, value: allocation.branch },
                          ]
                        )}
                        className={classNames("truncate text-foreground", plainLinkStyle)}
                        title={holderLabel}
                      >
                        {holderLabel}
                      </Link>
                    </Cell>
                    <Cell className={classNames(cellStyle, "text-foreground-muted")}>
                      <KindLabel kind={allocation.holder.__typename} />
                    </Cell>
                    <Cell className={cellStyle}>
                      <Link
                        to={getBranchDetailsUrl(allocation.branch)}
                        className={classNames(
                          "truncate text-foreground-muted transition-colors duration-100 hover:text-foreground",
                          plainLinkStyle
                        )}
                        title={allocation.branch}
                      >
                        {allocation.branch}
                      </Link>
                    </Cell>
                    {showRangeColumn && (
                      <Cell className={classNames(cellStyle, "text-foreground-muted tabular-nums")}>
                        {range ? formatSpan(range) : ""}
                      </Cell>
                    )}
                    <Cell className={cellStyle}>
                      <SourceTag provenance={allocation.provenance} />
                    </Cell>
                  </AriaRow>
                );
              }}
            </Collection>
            {hasNextPage && (
              <TableLoadMoreItem
                onLoadMore={fetchNextPage}
                isLoading={isFetchingNextPage}
                className="flex items-center justify-center gap-2 text-foreground-muted text-xs"
              >
                <Spinner className="size-3.5" /> Loading more
              </TableLoadMoreItem>
            )}
          </TableBody>
        </Table>
      </Virtualizer>
    </Col>
  );
}

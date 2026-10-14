import { ArrowDownIcon, ArrowUpIcon } from "lucide-react";
import type React from "react";
import { useNavigate } from "react-router";

import { Col } from "@/shared/components/container";
import { Link } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";

import type {
  NumberPoolDivision,
  NumberPoolDivisionEntry,
} from "@/entities/resource-manager/domain/model/number-pool";
import {
  NUMBER_POOL_DIVISION_SORT_BY_USAGE,
  type NumberPoolDivisionSort,
} from "@/entities/resource-manager/ui/hooks/use-number-pool-division-table-state";
import type { NumberPoolScopeField } from "@/entities/resource-manager/ui/hooks/use-number-pool-scope-fields";
import { NumberPoolUsageBar } from "@/entities/resource-manager/ui/number-pool/details/number-pool-usage-bar";
import { getNumberPoolDivisionUrl } from "@/entities/resource-manager/ui/routing/number-pool-urls";

// a collapsed table border stays with the table, so the pinned column draws its own edge
const pinnedEdge =
  "before:pointer-events-none before:absolute before:inset-y-0 before:left-0 before:w-px before:bg-border";

// the table surface is slightly translucent in dark mode; a pinned cell needs the same colour fully opaque
const pinnedSurface: React.CSSProperties = {
  background:
    "linear-gradient(var(--table-cell-pinned), var(--table-cell-pinned)), var(--color-black)",
};

// a collapsed table border scrolls away with the body, so the sticky header draws its own bottom edge
const headerCellStyle =
  "relative h-8 whitespace-nowrap px-3 text-left font-medium text-foreground-muted text-xs after:pointer-events-none after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-border";

const usageCellStyle = classNames("sticky right-0 w-64 min-w-64", pinnedEdge);

interface SortHeaderProps {
  label: string;
  sortBy: string;
  sort: NumberPoolDivisionSort;
  onSortChange: (sort: NumberPoolDivisionSort) => void;
  className?: string;
  style?: React.CSSProperties;
}

function SortHeader({ label, sortBy, sort, onSortChange, className, style }: SortHeaderProps) {
  const isSorted = sort.by === sortBy;
  const SortIcon = sort.direction === "ascending" ? ArrowUpIcon : ArrowDownIcon;

  const toggle = () => {
    if (isSorted) {
      onSortChange({
        by: sortBy,
        direction: sort.direction === "ascending" ? "descending" : "ascending",
      });
      return;
    }
    onSortChange({
      by: sortBy,
      direction: sortBy === NUMBER_POOL_DIVISION_SORT_BY_USAGE ? "descending" : "ascending",
    });
  };

  return (
    <th
      className={classNames(headerCellStyle, className)}
      style={style}
      aria-sort={isSorted ? sort.direction : undefined}
    >
      <button
        type="button"
        onClick={toggle}
        className="inline-flex items-center gap-1 rounded-sm outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring-halo"
      >
        {label}
        {isSorted && <SortIcon className="size-3" aria-hidden />}
      </button>
    </th>
  );
}

interface EntryValueProps {
  entry: NumberPoolDivisionEntry | undefined;
}

function EntryValue({ entry }: EntryValueProps) {
  const label = entry?.label ?? "";

  return (
    <Col className="min-w-0 gap-0">
      <span
        className={classNames("truncate", label === "" && "text-foreground-muted italic")}
        title={label || undefined}
      >
        {label || "No value"}
      </span>
      {entry?.peerKind && (
        <span className="truncate font-mono text-foreground-muted text-xxs">{entry.peerKind}</span>
      )}
    </Col>
  );
}

const isOpenedByTheBrowser = (event: React.MouseEvent) =>
  event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0;

export interface NumberPoolDivisionsTableProps {
  poolId: string;
  fields: NumberPoolScopeField[];
  divisions: NumberPoolDivision[];
  sort: NumberPoolDivisionSort;
  onSortChange: (sort: NumberPoolDivisionSort) => void;
}

export function NumberPoolDivisionsTable({
  poolId,
  fields,
  divisions,
  sort,
  onSortChange,
}: NumberPoolDivisionsTableProps) {
  const navigate = useNavigate();

  return (
    <table className="min-w-full border-collapse">
      <thead className="sticky top-0 z-20 bg-table-cell-pinned">
        <tr>
          {fields.map((field) => (
            <SortHeader
              key={field.name}
              label={field.label}
              sortBy={field.name}
              sort={sort}
              onSortChange={onSortChange}
            />
          ))}
          <SortHeader
            label="Usage"
            sortBy={NUMBER_POOL_DIVISION_SORT_BY_USAGE}
            sort={sort}
            onSortChange={onSortChange}
            className={classNames("z-10", usageCellStyle)}
            style={pinnedSurface}
          />
        </tr>
      </thead>
      <tbody className="bg-table-cell-pinned">
        {divisions.map((division) => {
          const values = division.entries.map((entry) => entry.value);
          const url = getNumberPoolDivisionUrl(poolId, values);

          return (
            <tr
              key={JSON.stringify(values)}
              className="cursor-pointer not-last:border-b hover:bg-highlight"
              onClick={(event) => {
                const isOnLink = (event.target as HTMLElement).closest("a") !== null;
                if (isOnLink || isOpenedByTheBrowser(event)) return;
                navigate(url);
              }}
            >
              {fields.map((field, index) => {
                const entry = division.entries.find(({ path }) => path === field.name);

                return (
                  <td key={field.name} className="h-11 max-w-64 whitespace-nowrap px-3 text-sm">
                    {index === 0 ? (
                      <Link to={url} className="block font-medium no-underline hover:underline">
                        <EntryValue entry={entry} />
                      </Link>
                    ) : (
                      <EntryValue entry={entry} />
                    )}
                  </td>
                );
              })}
              <td className={classNames("px-3", usageCellStyle)} style={pinnedSurface}>
                <NumberPoolUsageBar usage={division.usage} />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

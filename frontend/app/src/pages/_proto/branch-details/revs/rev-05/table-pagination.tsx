// PROTOTYPE — copied from the IFC-3130 worktree (shared/components/table/table-pagination.tsx and
// shared/utils/table-pagination.ts). `Icon` and the `foreground-muted`/`border` tokens aren't on this
// branch yet, so lucide chevrons and neutral classes stand in. Delete once IFC-3130 lands.
import { buttonVariants } from "@infrahub/ui";
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";

import { classNames } from "@/shared/utils/common";
import { formatNumberDisplay } from "@/shared/utils/number";

export const PAGE_SIZE = 10;
export const CELL_HEIGHT_PX = 40;

type PageItem = number | "ellipsis";

const toPageNumber = (page: number) => (Number.isFinite(page) ? Math.max(1, Math.trunc(page)) : 1);

export const getTotalPages = (totalCount: number, pageSize: number) =>
  Math.max(1, Math.ceil(Math.max(totalCount, 0) / pageSize));

export const clampPage = (page: number, totalPages: number) =>
  Math.min(toPageNumber(page), toPageNumber(totalPages));

const formatPageWindow = (page: number, pageSize: number, totalCount: number) => {
  const currentPage = clampPage(page, getTotalPages(totalCount, pageSize));
  const rows = Math.max(totalCount, 0);
  const firstRow = rows === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const lastRow = Math.min(currentPage * pageSize, rows);
  if (firstRow === lastRow)
    return `Showing ${formatNumberDisplay(firstRow)} of ${formatNumberDisplay(rows)}`;
  return `Showing ${formatNumberDisplay(firstRow)} to ${formatNumberDisplay(lastRow)} of ${formatNumberDisplay(rows)}`;
};

const getPageItems = (page: number, totalPages: number, siblingCount = 1): PageItem[] => {
  const lastPage = toPageNumber(totalPages);
  const currentPage = clampPage(page, lastPage);
  const rangeStart = Math.max(currentPage - siblingCount, 1);
  const rangeEnd = Math.min(currentPage + siblingCount, lastPage);
  const items: PageItem[] = [];
  if (rangeStart > 1) {
    items.push(1);
    if (rangeStart > 2) items.push("ellipsis");
  }
  for (let candidate = rangeStart; candidate <= rangeEnd; candidate++) items.push(candidate);
  if (rangeEnd < lastPage) {
    if (rangeEnd < lastPage - 1) items.push("ellipsis");
    items.push(lastPage);
  }
  return items;
};

const controlStyle = classNames(
  buttonVariants({ variant: "ghost", size: "sm", shape: "square" }),
  "hover:bg-neutral-100 disabled:pointer-events-none disabled:opacity-60"
);

const activePageStyle = classNames(
  buttonVariants({ variant: "outline", size: "sm", shape: "square" }),
  "font-medium"
);

export function TablePagination({
  page,
  pageSize,
  totalCount,
  onPageChange,
  className,
}: {
  page: number;
  pageSize: number;
  totalCount: number;
  onPageChange: (page: number) => void;
  className?: string;
}) {
  const totalPages = getTotalPages(totalCount, pageSize);
  const currentPage = clampPage(page, totalPages);

  return (
    <nav
      aria-label="Pagination"
      className={classNames(
        "flex flex-wrap items-center justify-between gap-2 p-2 text-sm",
        className
      )}
    >
      <p className="text-neutral-500 tabular-nums" role="status">
        {formatPageWindow(currentPage, pageSize, totalCount)}
      </p>

      <div className="flex items-center gap-1">
        <button
          aria-label="Previous page"
          className={controlStyle}
          disabled={currentPage <= 1}
          onClick={() => onPageChange(currentPage - 1)}
          type="button"
        >
          <ChevronLeftIcon className="size-4" />
        </button>

        {getPageItems(currentPage, totalPages).map((item, index) =>
          item === "ellipsis" ? (
            <span aria-hidden="true" className="px-1 text-neutral-500" key={`ellipsis-${index}`}>
              …
            </span>
          ) : (
            <button
              aria-current={item === currentPage ? "page" : undefined}
              aria-label={`Page ${item}`}
              className={item === currentPage ? activePageStyle : controlStyle}
              key={item}
              onClick={() => onPageChange(item)}
              type="button"
            >
              {item}
            </button>
          )
        )}

        <button
          aria-label="Next page"
          className={controlStyle}
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange(currentPage + 1)}
          type="button"
        >
          <ChevronRightIcon className="size-4" />
        </button>
      </div>
    </nav>
  );
}

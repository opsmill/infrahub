import { buttonVariants, Select, SelectItem, SelectList, SelectTrigger } from "@infrahub/ui";

import { Icon } from "@/shared/components/display/icon";
import { classNames } from "@/shared/utils/common";
import {
  clampPage,
  formatPageWindow,
  getPageItems,
  getTotalPages,
  PAGE_SIZE_OPTIONS,
} from "@/shared/utils/table-pagination";

export interface TablePaginationProps {
  page: number;
  pageSize: number;
  totalCount: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  className?: string;
}

const controlStyle = classNames(
  buttonVariants({ variant: "ghost", size: "sm", shape: "square" }),
  "hover:bg-border disabled:pointer-events-none disabled:opacity-60"
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
  onPageSizeChange,
  className,
}: TablePaginationProps) {
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
      <div className="flex items-center gap-2">
        <p className="text-foreground-muted" role="status">
          {formatPageWindow(currentPage, pageSize, totalCount)}
        </p>

        <Select
          aria-label="Rows per page"
          onChange={(value) => {
            onPageSizeChange(Number(value));
          }}
          value={pageSize}
        >
          <SelectTrigger className="w-auto" size="sm" />

          <SelectList width="content">
            {PAGE_SIZE_OPTIONS.map((option) => (
              <SelectItem id={option} key={option}>
                {String(option)}
              </SelectItem>
            ))}
          </SelectList>
        </Select>
      </div>

      <div className="flex items-center gap-1">
        <button
          aria-label="Previous page"
          className={controlStyle}
          disabled={currentPage <= 1}
          onClick={() => {
            onPageChange(currentPage - 1);
          }}
          type="button"
        >
          <Icon icon="mdi:chevron-left" />
        </button>

        {getPageItems(currentPage, totalPages).map((item, index) =>
          item === "ellipsis" ? (
            <span
              aria-hidden="true"
              className="px-1 text-foreground-muted"
              key={`ellipsis-${index}`}
            >
              …
            </span>
          ) : (
            <button
              aria-current={item === currentPage ? "page" : undefined}
              aria-label={`Page ${item}`}
              className={item === currentPage ? activePageStyle : controlStyle}
              key={item}
              onClick={() => {
                onPageChange(item);
              }}
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
          onClick={() => {
            onPageChange(currentPage + 1);
          }}
          type="button"
        >
          <Icon icon="mdi:chevron-right" />
        </button>
      </div>
    </nav>
  );
}

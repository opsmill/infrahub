import { buttonVariants } from "@infrahub/ui";
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";

import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";
import {
  clampPage,
  formatPageWindow,
  getPageItems,
  getTotalPages,
} from "@/shared/utils/table-pagination";

interface TablePaginationProps {
  page: number;
  pageSize: number;
  totalCount: number;
  onPageChange: (page: number) => void;
  className?: string;
  "aria-label"?: string;
}

const controlStyle = classNames(
  buttonVariants({ variant: "ghost", size: "sm", shape: "square" }),
  focusVisibleStyle,
  "hover:bg-content-muted disabled:pointer-events-none disabled:opacity-60"
);

const activePageStyle = classNames(
  buttonVariants({ variant: "outline", size: "sm", shape: "square" }),
  focusVisibleStyle,
  "font-medium"
);

export function TablePagination({
  page,
  pageSize,
  totalCount,
  onPageChange,
  className,
  "aria-label": ariaLabel = "Pagination",
}: TablePaginationProps) {
  const totalPages = getTotalPages(totalCount, pageSize);
  const currentPage = clampPage(page, totalPages);

  return (
    <nav
      aria-label={ariaLabel}
      className={classNames(
        "flex flex-wrap items-center justify-between gap-2 p-2 text-sm",
        className
      )}
    >
      <p className="text-foreground-muted tabular-nums" role="status">
        {formatPageWindow(currentPage, pageSize, totalCount)}
      </p>

      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-label="Previous page"
          className={controlStyle}
          disabled={currentPage <= 1}
          onClick={() => onPageChange(currentPage - 1)}
        >
          <ChevronLeftIcon className="size-4" />
        </button>

        {getPageItems(currentPage, totalPages).map((item, index) =>
          item === "ellipsis" ? (
            <span
              key={`ellipsis-${index}`}
              aria-hidden="true"
              className="px-1 text-foreground-muted"
            >
              …
            </span>
          ) : (
            <button
              key={item}
              type="button"
              aria-label={`Page ${item}`}
              aria-current={item === currentPage ? "page" : undefined}
              className={item === currentPage ? activePageStyle : controlStyle}
              onClick={() => onPageChange(item)}
            >
              {item}
            </button>
          )
        )}

        <button
          type="button"
          aria-label="Next page"
          className={controlStyle}
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange(currentPage + 1)}
        >
          <ChevronRightIcon className="size-4" />
        </button>
      </div>
    </nav>
  );
}

import { formatNumberDisplay } from "@/shared/utils/number";

export const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;

export const DEFAULT_PAGE_SIZE = 20;

export type PageSize = (typeof PAGE_SIZE_OPTIONS)[number];

export type PageItem = number | "ellipsis";

export interface PageWindow {
  firstRow: number;
  lastRow: number;
  totalCount: number;
}

export const isPageSize = (value: number): value is PageSize =>
  PAGE_SIZE_OPTIONS.some((option) => option === value);

export const toPageNumber = (page: number) =>
  Number.isFinite(page) ? Math.max(1, Math.trunc(page)) : 1;

export const getTotalPages = (totalCount: number, pageSize: number) =>
  Math.max(1, Math.ceil(Math.max(totalCount, 0) / pageSize));

export const clampPage = (page: number, totalPages: number) =>
  Math.min(toPageNumber(page), toPageNumber(totalPages));

export const getOffset = (page: number, pageSize: number) => (toPageNumber(page) - 1) * pageSize;

export const getPageFromOffset = (offset: number, pageSize: number) =>
  Math.floor(Math.max(offset, 0) / pageSize) + 1;

export const getPageWindow = (page: number, pageSize: number, totalCount: number): PageWindow => {
  const currentPage = clampPage(page, getTotalPages(totalCount, pageSize));
  const rows = Math.max(totalCount, 0);

  return {
    firstRow: rows === 0 ? 0 : (currentPage - 1) * pageSize + 1,
    lastRow: Math.min(currentPage * pageSize, rows),
    totalCount: rows,
  };
};

export const formatPageWindow = (page: number, pageSize: number, totalCount: number) => {
  const { firstRow, lastRow, totalCount: rows } = getPageWindow(page, pageSize, totalCount);

  if (firstRow === lastRow) {
    return `Showing ${formatNumberDisplay(firstRow)} of ${formatNumberDisplay(rows)}`;
  }

  return `Showing ${formatNumberDisplay(firstRow)} to ${formatNumberDisplay(lastRow)} of ${formatNumberDisplay(rows)}`;
};

export const getPageItems = (page: number, totalPages: number, siblingCount = 1): PageItem[] => {
  const lastPage = toPageNumber(totalPages);
  const currentPage = clampPage(page, lastPage);
  const rangeStart = Math.max(currentPage - siblingCount, 1);
  const rangeEnd = Math.min(currentPage + siblingCount, lastPage);
  const items: PageItem[] = [];

  if (rangeStart > 1) {
    items.push(1);

    if (rangeStart > 2) {
      items.push("ellipsis");
    }
  }

  for (let candidate = rangeStart; candidate <= rangeEnd; candidate++) {
    items.push(candidate);
  }

  if (rangeEnd < lastPage) {
    if (rangeEnd < lastPage - 1) {
      items.push("ellipsis");
    }

    items.push(lastPage);
  }

  return items;
};

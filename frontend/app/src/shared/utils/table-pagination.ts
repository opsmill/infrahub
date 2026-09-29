import { formatNumberDisplay } from "@/shared/utils/number";

export const TABLE_PAGE_SIZE = 10;
export const TABLE_ROW_HEIGHT_PX = 40;

type PageItem = number | "ellipsis";

export const toPageNumber = (page: number) =>
  Number.isFinite(page) ? Math.max(1, Math.trunc(page)) : 1;

export const getTotalPages = (totalCount: number, pageSize: number) =>
  Math.max(1, Math.ceil(Math.max(totalCount, 0) / pageSize));

export const clampPage = (page: number, totalPages: number) =>
  Math.min(toPageNumber(page), toPageNumber(totalPages));

export const getPageItems = (page: number, totalPages: number, siblingCount = 1): PageItem[] => {
  const lastPage = toPageNumber(totalPages);
  const currentPage = clampPage(page, lastPage);
  const rangeStart = Math.max(currentPage - siblingCount, 1);
  const rangeEnd = Math.min(currentPage + siblingCount, lastPage);

  const items: PageItem[] = [];
  if (rangeStart > 1) {
    items.push(1);
    if (rangeStart > 2) items.push("ellipsis");
  }
  for (let item = rangeStart; item <= rangeEnd; item++) items.push(item);
  if (rangeEnd < lastPage) {
    if (rangeEnd < lastPage - 1) items.push("ellipsis");
    items.push(lastPage);
  }
  return items;
};

export const formatPageWindow = (page: number, pageSize: number, totalCount: number) => {
  const rows = Math.max(totalCount, 0);
  const currentPage = clampPage(page, getTotalPages(rows, pageSize));
  const firstRow = rows === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const lastRow = Math.min(currentPage * pageSize, rows);

  if (firstRow === lastRow) {
    return `Showing ${formatNumberDisplay(firstRow)} of ${formatNumberDisplay(rows)}`;
  }
  return `Showing ${formatNumberDisplay(firstRow)} to ${formatNumberDisplay(lastRow)} of ${formatNumberDisplay(rows)}`;
};

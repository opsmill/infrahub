import { useEffect } from "react";

import { clampPage } from "@/shared/utils/table-pagination";

// The last page is only known once the total has loaded, so an out-of-range page from the URL
// can't be derived away before the fetch; it is written back so the URL names the page shown.
export function usePageInRange(
  page: number,
  totalPages: number | null,
  onPageChange: (page: number) => void
) {
  const validPage = totalPages === null ? null : clampPage(page, totalPages);

  useEffect(() => {
    if (validPage !== null && validPage !== page) onPageChange(validPage);
  }, [validPage, page, onPageChange]);
}

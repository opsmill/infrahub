import { formatNumberDisplay } from "@/shared/utils/number";

interface SearchResultsWindow {
  offset: number;
  rowCount: number;
}

// The search returns no total, so the text names the listed rows without "of N".
export function formatSearchResultsWindow({ offset, rowCount }: SearchResultsWindow): string {
  const firstRow = offset + 1;
  const lastRow = offset + rowCount;

  if (firstRow === lastRow) return `Showing result ${formatNumberDisplay(firstRow)}`;

  return `Showing results ${formatNumberDisplay(firstRow)} to ${formatNumberDisplay(lastRow)}`;
}

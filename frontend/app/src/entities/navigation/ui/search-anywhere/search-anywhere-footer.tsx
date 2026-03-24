import { Icon } from "@iconify-icon/react";
import { useCommandState } from "cmdk";
import { useAtomValue } from "jotai";
import { Link } from "react-router";

import { useDebounce } from "@/shared/hooks/useDebounce";

import { searchResultCountAtom } from "@/entities/navigation/stores/search-result-count.atom";
import { useSearchAnywhereContext } from "@/entities/navigation/ui/search-anywhere/search-anywhere-context";

export function SearchAnywhereFooter() {
  const query = useCommandState((state) => state.search);
  const queryDebounced = useDebounce(query.trim(), 300);
  const count = useAtomValue(searchResultCountAtom);
  const { closeDialog } = useSearchAnywhereContext();

  if (!queryDebounced || count <= 0) {
    return null;
  }

  return (
    <div className="border-gray-200 border-t px-2 py-1">
      <Link
        to={`/search?q=${encodeURIComponent(queryDebounced)}`}
        onClick={closeDialog}
        className="flex items-center justify-center gap-1 rounded px-2 py-1 text-custom-blue-700 text-xs hover:bg-gray-100"
      >
        <span>
          View all {count} {count === 1 ? "result" : "results"}
        </span>
        <Icon icon="mdi:arrow-right" className="text-sm" />
      </Link>
    </div>
  );
}

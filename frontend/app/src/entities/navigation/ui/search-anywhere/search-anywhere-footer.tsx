import { Icon } from "@iconify-icon/react";
import { useCommandState } from "cmdk";
import { useAtomValue } from "jotai";
import { Link } from "react-router";

import { useDebounce } from "@/shared/hooks/useDebounce";

import { useGetSearchAnywhere } from "@/entities/navigation/domain/search-anywhere.query";
import { searchCaseSensitiveAtom } from "@/entities/navigation/stores/search-case-sensitive.atom";
import { useSearchAnywhereContext } from "@/entities/navigation/ui/search-anywhere/search-anywhere-context";

export function SearchAnywhereFooter() {
  const query = useCommandState((state) => state.search);
  const queryDebounced = useDebounce(query.trim(), 300);
  const caseSensitive = useAtomValue(searchCaseSensitiveAtom);
  const { closeDialog } = useSearchAnywhereContext();

  const { data } = useGetSearchAnywhere(
    { search: queryDebounced, caseSensitive },
    { enabled: !!queryDebounced }
  );

  if (!queryDebounced || !data || data.count <= 0) {
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
          View all {data.count} {data.count === 1 ? "result" : "results"}
        </span>
        <Icon icon="mdi:arrow-right" className="text-sm" />
      </Link>
    </div>
  );
}

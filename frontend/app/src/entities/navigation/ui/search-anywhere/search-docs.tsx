import { useCommandState } from "cmdk";

import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";
import { useDebounce } from "@/shared/hooks/useDebounce";

import { useGetSearchDocs } from "@/entities/navigation/domain/search-docs.query";
import { SearchAnywhereGroup } from "@/entities/navigation/ui/search-anywhere/search-anywhere-group";
import { SearchAnywhereItem } from "@/entities/navigation/ui/search-anywhere/search-anywhere-item";

export const SearchDocs = () => {
  const query = useCommandState((state) => state.search);
  const queryDebounced = useDebounce(query, 300);
  const { data: results, error, isPending } = useGetSearchDocs({ query: queryDebounced });

  if (query === "") {
    return null;
  }

  if (isPending) {
    return (
      <SearchAnywhereGroup heading="Documentation">
        <SearchAnywhereItem to="" disabled>
          Loading...
        </SearchAnywhereItem>
      </SearchAnywhereGroup>
    );
  }

  if (error || !Array.isArray(results) || results.length === 0) return null;

  return (
    <SearchAnywhereGroup heading="Documentation">
      {results.map((doc) => (
        <SearchAnywhereItem
          key={doc.title + doc.url}
          value={doc.url}
          to={INFRAHUB_API_SERVER_URL + doc.url}
          className="flex-col items-start gap-0"
        >
          <div className="font-medium text-sm">{doc.title}</div>
          <div className="truncate text-neutral-500 text-xs">
            {doc.breadcrumb.slice(1).join(" > ")}
          </div>
        </SearchAnywhereItem>
      ))}
    </SearchAnywhereGroup>
  );
};

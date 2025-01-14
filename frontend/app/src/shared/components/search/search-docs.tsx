import { INFRAHUB_API_SERVER_URL } from "@/config/config";
import { searchDocsQueryOptions } from "@/shared/components/search/queries/get-doc-results";
import { SearchAnywhereGroup } from "@/shared/components/search/search-anywhere-group";
import { SearchAnywhereItem } from "@/shared/components/search/search-anywhere-item";
import { useDebounce } from "@/shared/hooks/useDebounce";
import { useQuery } from "@tanstack/react-query";
import { useCommandState } from "cmdk";

export const SearchDocs = () => {
  const query = useCommandState((state) => state.search);
  const queryDebounced = useDebounce(query, 300);
  const {
    data: results,
    error,
    isPending,
  } = useQuery(searchDocsQueryOptions({ query: queryDebounced }));

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

  if (error || results.length === 0) return null;

  return (
    <SearchAnywhereGroup heading="Documentation">
      {results.map((doc) => (
        <SearchAnywhereItem
          key={doc.title + doc.url}
          value={doc.url}
          to={INFRAHUB_API_SERVER_URL + doc.url}
          className="flex-col gap-0 items-start"
        >
          <div className="text-sm font-medium">{doc.title}</div>
          <div className="text-xs truncate text-neutral-500">
            {doc.breadcrumb.slice(1).join(" > ")}
          </div>
        </SearchAnywhereItem>
      ))}
    </SearchAnywhereGroup>
  );
};

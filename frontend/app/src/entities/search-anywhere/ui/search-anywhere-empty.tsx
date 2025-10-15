import { Icon } from "@iconify-icon/react";
import { useCommandState } from "cmdk";

import { INFRAHUB_API_SERVER_URL } from "@/config/config";

import { SearchAnywhereGroup } from "@/entities/search-anywhere/ui/search-anywhere-group";
import { SearchAnywhereItem } from "@/entities/search-anywhere/ui/search-anywhere-item";

export function SearchAnywhereEmpty() {
  const count = useCommandState((state) => state.filtered.count);
  const query = useCommandState((state) => state.search);

  if (query === "" || count !== 0) return null;

  return (
    <SearchAnywhereGroup>
      <SearchAnywhereItem forceMount to={`${INFRAHUB_API_SERVER_URL}/docs/search?q=${query}`}>
        <Icon icon="mdi:book-open-blank-variant-outline" className="text-lg" />
        Search in docs: <span className="font-semibold">{query}</span>
      </SearchAnywhereItem>
    </SearchAnywhereGroup>
  );
}

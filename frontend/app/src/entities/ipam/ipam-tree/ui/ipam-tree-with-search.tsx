import React from "react";
import { useParams } from "react-router";

import { SearchInput } from "@/shared/components/inputs/search-input";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { useDebounce } from "@/shared/hooks/useDebounce";

import { IpamTree } from "@/entities/ipam/ipam-tree/ui/ipam-tree";

export function IpamTreeWithSearch() {
  const { objectId } = useParams();
  const [search, setSearch] = React.useState("");
  const searchDebounced = useDebounce(search, 300);

  return (
    <>
      <div className="p-1">
        <SearchInput
          placeholder="Filter..."
          className="border-transparent"
          value={search}
          onChange={setSearch}
          aria-label="IPAM Tree search"
        />
      </div>

      <ScrollArea scrollX>
        <IpamTree currentNodeId={objectId} search={searchDebounced} className="p-1" />
      </ScrollArea>
    </>
  );
}

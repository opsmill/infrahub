import { useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import type React from "react";
import { useState } from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { Badge } from "@/shared/components/ui/badge";
import { ComboboxEmpty, ComboboxItem } from "@/shared/components/ui/combobox";
import { Command, CommandInput, CommandList } from "@/shared/components/ui/command";
import { Spinner } from "@/shared/components/ui/spinner";
import { debounce } from "@/shared/utils/common";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getRelationshipsInfiniteQueryOptions } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships.query";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { NodeSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import {
  getRootSchemaOfHierarchicalSchema,
  isHierarchicalSchema,
} from "@/entities/schema/utils/is-hierarchical-schema";

export interface RelationshipHierarchicalComboboxListProps {
  peer: string;
  onSelect: (value: RelationshipNode) => void;
  value?: RelationshipNode | null;
  filterItem?: (relationshipNode: RelationshipNode) => boolean;
}

export const RelationshipHierarchicalComboboxList = ({
  peer,
  value,
  onSelect,
  filterItem,
}: RelationshipHierarchicalComboboxListProps) => {
  const { isNode, schema: peerSchema } = useSchema(peer);
  if (!isNode || !peerSchema || !isHierarchicalSchema(peerSchema)) {
    return <div>This schema is not a node with hierarchy</div>;
  }

  const rootSchema = getRootSchemaOfHierarchicalSchema(peerSchema);

  return (
    <HierarchicalExplorer
      topLevelSchema={rootSchema}
      targetSchema={peerSchema}
      onSelect={onSelect}
      value={value}
      filterItem={filterItem}
    />
  );
};

type HierarchicalExplorerProps = {
  topLevelSchema: NodeSchema;
  topLevelNode?: RelationshipNode;
  targetSchema: NodeSchema;
  removeSelectedNode?: () => void;
  onSelect: (relationshipNode: RelationshipNode) => void;
  value?: RelationshipNode | null;
  filterItem?: (relationshipNode: RelationshipNode) => boolean;
};

const HierarchicalExplorer = ({
  topLevelSchema,
  topLevelNode,
  targetSchema,
  onSelect,
  value,
  filterItem,
  removeSelectedNode,
}: HierarchicalExplorerProps) => {
  const peer = topLevelNode ? topLevelSchema.children : topLevelSchema.kind;
  const nodeSchemas = useAtomValue(nodeSchemasAtom);
  const { currentBranch } = useCurrentBranch();
  const branchName = currentBranch.name;
  const [search, setSearch] = useState("");
  const queryOptions = search
    ? getRelationshipsInfiniteQueryOptions({
        peer: topLevelSchema.hierarchy as string,
        search,
        branchName,
      })
    : getRelationshipsInfiniteQueryOptions({
        peer: peer as string,
        branchName,
        ...(topLevelNode ? { filterQuery: { parent__ids: [topLevelNode.id] } } : {}),
      });

  const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInfiniteQuery(queryOptions);
  const [selectNode, setSelectNode] = useState<RelationshipNode>();

  if (selectNode) {
    const selectedNodeSchema = nodeSchemas.find((schema) => schema.kind === selectNode.__typename);

    if (!selectedNodeSchema) {
      return <div>Selected node's schema not found (kind: {selectNode.__typename})</div>;
    }

    const handleRemoveNode = () => {
      setSearch("");
      setSelectNode(undefined);
    };

    return (
      <>
        <Badge className="mt-1 ml-2 cursor-pointer self-start" onClick={handleRemoveNode}>
          {selectNode.display_label} &times;
        </Badge>

        <HierarchicalExplorer
          topLevelSchema={selectedNodeSchema}
          topLevelNode={selectNode}
          targetSchema={targetSchema}
          onSelect={onSelect}
          value={value}
          removeSelectedNode={handleRemoveNode}
          filterItem={filterItem}
        />
      </>
    );
  }

  if (error) return <ErrorScreen message={error.message} />;

  const setSearchDebounced = debounce(setSearch, 300);

  const handleSelect = (relationshipNode: RelationshipNode) => {
    if (relationshipNode.__typename === targetSchema.kind) {
      onSelect(relationshipNode);
      return;
    }

    setSelectNode(relationshipNode);
  };

  return (
    <Command
      shouldFilter={false}
      onKeyDown={(e: React.KeyboardEvent) => {
        if (search.length) return;

        if (e.key === "Backspace") {
          e.preventDefault();
          removeSelectedNode?.();
        }
      }}
    >
      <CommandInput autoFocus placeholder="Filter..." onValueChange={setSearchDebounced} />

      <CommandList>
        {isPending ? (
          <Spinner className="m-2 flex justify-center" />
        ) : (
          <>
            <ComboboxEmpty>No results found</ComboboxEmpty>

            {data.pages.map((page) => {
              const filteredNodes = filterItem ? page.filter(filterItem) : page;

              return filteredNodes.map((node) => {
                const schema = nodeSchemas.find((schema) => schema.kind === node.__typename);
                return (
                  <ComboboxItem
                    key={node.id}
                    value={node.id}
                    selectedValue={value?.id}
                    onSelect={() => handleSelect(node)}
                  >
                    <span className="truncate">{node.display_label}</span>
                    <span className="ml-auto text-gray-500 text-xs">{schema?.label}</span>
                  </ComboboxItem>
                );
              });
            })}
          </>
        )}

        {hasNextPage && (
          <ComboboxItem
            value="Load more"
            onSelect={() => fetchNextPage()}
            disabled={!hasNextPage || isFetchingNextPage}
            className="justify-center text-custom-blue-700"
          >
            {isFetchingNextPage ? "Loading more..." : "Load more"}
          </ComboboxItem>
        )}
      </CommandList>
    </Command>
  );
};

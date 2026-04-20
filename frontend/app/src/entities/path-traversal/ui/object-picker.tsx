import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { jsonToGraphQLQuery } from "json-to-graphql-query";
import { useEffect, useState } from "react";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

type ObjectPickerProps = {
  label: string;
  value: string;
  displayLabel?: string;
  onChange: (id: string, displayLabel: string) => void;
};

/** Resolve a UUID to its kind and display_label via CoreNode query */
async function resolveUuid(
  uuid: string,
  branchName: string
): Promise<{ kind: string; displayLabel: string } | null> {
  const queryString = jsonToGraphQLQuery({
    query: {
      CoreNode: {
        __args: { ids: [uuid] },
        edges: { node: { __typename: true, display_label: true } },
      },
    },
  });

  const { data } = await graphqlClient.query({
    query: gql(queryString),
    context: { branch: branchName },
  });

  const result = data?.CoreNode?.edges?.[0]?.node;
  if (!result) return null;

  return {
    kind: result.__typename ?? "",
    displayLabel: result.display_label ?? result.__typename ?? "",
  };
}

export function ObjectPicker({ label, value, displayLabel, onChange }: ObjectPickerProps) {
  const [mode, setMode] = useState<"search" | "uuid">("search");
  const [selectedKind, setSelectedKind] = useState("");
  const [kindOpen, setKindOpen] = useState(false);
  const [objectOpen, setObjectOpen] = useState(false);
  const [uuidInput, setUuidInput] = useState(value);
  const [isResolving, setIsResolving] = useState(false);

  const nodeSchemas = useAtomValue(nodeSchemasAtom);
  const { currentBranch } = useCurrentBranch();

  // Auto-resolve UUID on mount when value exists but no displayLabel
  useEffect(() => {
    if (value && !displayLabel) {
      setIsResolving(true);
      resolveUuid(value, currentBranch.name)
        .then((resolved) => {
          if (resolved) {
            onChange(value, resolved.displayLabel);
          }
        })
        .catch(() => {})
        .finally(() => setIsResolving(false));
    }
  }, []); // Only on mount

  function handleSelectObject(object: RelationshipNode) {
    const objectLabel = getNodeLabel(object);
    onChange(object.id, objectLabel);
    setObjectOpen(false);
  }

  async function handleUuidSubmit() {
    const trimmed = uuidInput.trim();
    if (!trimmed) return;

    setIsResolving(true);
    try {
      const resolved = await resolveUuid(trimmed, currentBranch.name);
      if (resolved) {
        onChange(trimmed, resolved.displayLabel);
      } else {
        onChange(trimmed, `${trimmed.slice(0, 8)}...`);
      }
    } catch {
      onChange(trimmed, `${trimmed.slice(0, 8)}...`);
    } finally {
      setIsResolving(false);
    }
  }

  function handleClear() {
    onChange("", "");
    setUuidInput("");
    setSelectedKind("");
  }

  const selectedSchema = nodeSchemas.find((s) => s.kind === selectedKind);
  const selectedDisplay = displayLabel || (value ? `${value.slice(0, 12)}...` : "");

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="block font-medium text-gray-700 text-sm">{label}</span>
        <button
          type="button"
          onClick={() => setMode(mode === "search" ? "uuid" : "search")}
          className="text-gray-400 text-xs hover:text-blue-600"
        >
          {mode === "search" ? "Paste UUID" : "Search"}
        </button>
      </div>

      {mode === "uuid" ? (
        <div className="relative">
          <input
            type="text"
            value={uuidInput}
            onChange={(e) => setUuidInput(e.target.value)}
            onBlur={() => handleUuidSubmit()}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleUuidSubmit();
            }}
            placeholder="Paste object UUID..."
            className="w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-xs focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {isResolving && (
            <span className="absolute top-1/2 right-3 -translate-y-1/2 text-gray-400 text-xs">
              Resolving...
            </span>
          )}
        </div>
      ) : (
        <div className="space-y-1.5">
          <Combobox open={kindOpen} onOpenChange={setKindOpen}>
            <ComboboxTrigger className="w-full">
              {selectedSchema ? (
                <span>{selectedSchema.label ?? selectedSchema.kind}</span>
              ) : (
                <span className="text-gray-400">Select a kind...</span>
              )}
            </ComboboxTrigger>
            <ComboboxContent>
              <ComboboxList>
                <ComboboxEmpty>No kinds found</ComboboxEmpty>
                {nodeSchemas.map((schema) => (
                  <ComboboxItem
                    key={schema.kind}
                    value={schema.kind as string}
                    selectedValue={selectedKind}
                    onSelect={() => {
                      setSelectedKind(schema.kind as string);
                      setKindOpen(false);
                      setObjectOpen(true);
                    }}
                  >
                    <span className="truncate">{schema.label ?? schema.kind}</span>
                    <span className="ml-auto text-gray-400 text-xs">{schema.namespace}</span>
                  </ComboboxItem>
                ))}
              </ComboboxList>
            </ComboboxContent>
          </Combobox>

          {selectedKind && (
            <Combobox open={objectOpen} onOpenChange={setObjectOpen}>
              <ComboboxTrigger className="w-full">
                {value ? (
                  <span className="truncate">{selectedDisplay}</span>
                ) : (
                  <span className="text-gray-400">Select an object...</span>
                )}
              </ComboboxTrigger>
              <ComboboxContent>
                <RelationshipComboboxList
                  peer={selectedKind}
                  value={value ? ({ id: value } as RelationshipNode) : null}
                  onSelect={handleSelectObject}
                />
              </ComboboxContent>
            </Combobox>
          )}
        </div>
      )}

      {value && (
        <div className="flex items-center gap-2 rounded bg-blue-50 px-2 py-1.5">
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium text-blue-800 text-xs">{selectedDisplay}</div>
            <div className="truncate font-mono text-blue-600 text-xs">{value}</div>
          </div>
          <button
            type="button"
            onClick={handleClear}
            className="flex-shrink-0 text-blue-400 text-xs hover:text-blue-600"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}

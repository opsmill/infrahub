import { useAtomValue } from "jotai";
import { useState } from "react";

import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

type NodePickerProps = {
  label: string;
  value: string;
  displayLabel?: string;
  onChange: (id: string, displayLabel: string) => void;
};

export function NodePicker({ label, value, displayLabel, onChange }: NodePickerProps) {
  const [mode, setMode] = useState<"search" | "uuid">("search");
  const [selectedKind, setSelectedKind] = useState("");
  const [kindOpen, setKindOpen] = useState(false);
  const [nodeOpen, setNodeOpen] = useState(false);
  const [uuidInput, setUuidInput] = useState(value);

  const nodeSchemas = useAtomValue(nodeSchemasAtom);

  function handleSelectNode(node: RelationshipNode) {
    const nodeLabel = getNodeLabel(node);
    onChange(node.id, nodeLabel);
    setNodeOpen(false);
  }

  function handleUuidSubmit() {
    const trimmed = uuidInput.trim();
    if (trimmed) {
      onChange(trimmed, trimmed.slice(0, 8) + "...");
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
        <input
          type="text"
          value={uuidInput}
          onChange={(e) => setUuidInput(e.target.value)}
          onBlur={handleUuidSubmit}
          onKeyDown={(e) => e.key === "Enter" && handleUuidSubmit()}
          placeholder="Paste node UUID..."
          className="w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-xs focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      ) : (
        <div className="space-y-1.5">
          {/* Kind selector using Combobox */}
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
                      setNodeOpen(true);
                    }}
                  >
                    <span className="truncate">{schema.label ?? schema.kind}</span>
                    <span className="ml-auto text-gray-400 text-xs">{schema.namespace}</span>
                  </ComboboxItem>
                ))}
              </ComboboxList>
            </ComboboxContent>
          </Combobox>

          {/* Node selector using RelationshipComboboxList */}
          {selectedKind && (
            <Combobox open={nodeOpen} onOpenChange={setNodeOpen}>
              <ComboboxTrigger className="w-full">
                {value ? (
                  <span className="truncate">{selectedDisplay}</span>
                ) : (
                  <span className="text-gray-400">Select a node...</span>
                )}
              </ComboboxTrigger>
              <ComboboxContent>
                <RelationshipComboboxList
                  peer={selectedKind}
                  value={value ? ({ id: value } as RelationshipNode) : null}
                  onSelect={handleSelectNode}
                />
              </ComboboxContent>
            </Combobox>
          )}
        </div>
      )}

      {/* Selected value chip */}
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

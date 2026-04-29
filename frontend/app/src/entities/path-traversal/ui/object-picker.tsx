import { useEffect, useState } from "react";

import { NodeKindSelect } from "@/shared/components/inputs/node-kind-select";
import { PeerInput } from "@/shared/components/inputs/peer";

import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";

type ObjectPickerProps = {
  label: string;
  value: string;
  displayLabel?: string;
  onChange: (id: string, displayLabel: string) => void;
};

export function ObjectPicker({ label, value, displayLabel, onChange }: ObjectPickerProps) {
  const [mode, setMode] = useState<"search" | "uuid">("search");
  const [selectedKind, setSelectedKind] = useState<string | null>(null);
  const [uuidInput, setUuidInput] = useState(value);

  const { data: resolvedNode, isFetching: isResolving } = useGetObject(
    { objectId: value, objectSchema: { kind: "CoreNode" } },
    { enabled: !!value && !displayLabel }
  );

  useEffect(() => {
    if (value && !displayLabel && resolvedNode?.display_label) {
      onChange(value, resolvedNode.display_label);
    }
  }, [value, displayLabel, resolvedNode?.display_label, onChange]);

  const peerValue: Node | null =
    value && displayLabel
      ? { id: value, display_label: displayLabel, __typename: selectedKind ?? "" }
      : null;

  function handlePeerChange(node: Node | null) {
    if (node) onChange(node.id, node.display_label);
    else onChange("", "");
  }

  function handleUuidSubmit() {
    const trimmed = uuidInput.trim();
    if (!trimmed) return;
    onChange(trimmed, "");
  }

  function handleClear() {
    onChange("", "");
    setUuidInput("");
    setSelectedKind(null);
  }

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
          <NodeKindSelect value={selectedKind} onChange={setSelectedKind} className="w-full" />

          {selectedKind && (
            <PeerInput
              peer={selectedKind}
              value={peerValue}
              onChange={handlePeerChange}
              className="w-full"
            />
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

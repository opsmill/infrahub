import { useAtomValue } from "jotai";
import { type FormEvent, useState } from "react";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { NodePicker } from "./node-picker";
import { HIDDEN_NAMESPACES } from "./utils";

type DependencySelectorProps = {
  onSearch: (params: { sourceId: string; targetKinds: string[]; maxDepth: number }) => void;
  isLoading: boolean;
  initialSourceId?: string;
};

export function DependencySelector({
  onSearch,
  isLoading,
  initialSourceId = "",
}: DependencySelectorProps) {
  const [sourceId, setSourceId] = useState(initialSourceId);
  const [sourceLabel, setSourceLabel] = useState("");
  const [selectedKinds, setSelectedKinds] = useState<string[]>([]);
  const [maxDepth, setMaxDepth] = useState(5);
  const [kindSearch, setKindSearch] = useState("");

  const allNodeSchemas = useAtomValue(nodeSchemasAtom);
  const nodeSchemas = allNodeSchemas.filter((s) => !HIDDEN_NAMESPACES.has(s.namespace as string));
  const filteredKinds = kindSearch
    ? nodeSchemas.filter(
        (s) =>
          (s.label ?? "").toLowerCase().includes(kindSearch.toLowerCase()) ||
          (s.kind ?? "").toLowerCase().includes(kindSearch.toLowerCase())
      )
    : nodeSchemas;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (sourceId && selectedKinds.length > 0) {
      onSearch({ sourceId, targetKinds: selectedKinds, maxDepth });
    }
  }

  function toggleKind(kind: string) {
    setSelectedKinds((prev) =>
      prev.includes(kind) ? prev.filter((k) => k !== kind) : [...prev, kind]
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 p-4">
      <NodePicker
        label="Source Node"
        value={sourceId}
        displayLabel={sourceLabel}
        onChange={(id, label) => {
          setSourceId(id);
          setSourceLabel(label);
        }}
      />

      <div>
        <span className="mb-1 block font-medium text-gray-700 text-sm">
          What kinds to find? {selectedKinds.length > 0 && `(${selectedKinds.length} selected)`}
        </span>
        <input
          type="text"
          value={kindSearch}
          onChange={(e) => setKindSearch(e.target.value)}
          placeholder="Search kinds..."
          className="mb-1 w-full rounded border border-gray-200 px-2 py-1 text-xs focus:border-blue-400 focus:outline-none"
        />
        <div className="max-h-48 overflow-y-auto rounded border border-gray-200">
          {filteredKinds.map((schema) => (
            <label
              key={schema.kind}
              className="flex cursor-pointer items-center gap-2 px-2 py-1.5 text-xs hover:bg-gray-50"
            >
              <input
                type="checkbox"
                checked={selectedKinds.includes(schema.kind as string)}
                onChange={() => toggleKind(schema.kind as string)}
                className="rounded border-gray-300"
              />
              <span className="truncate">{schema.label ?? schema.kind}</span>
              <span className="ml-auto text-gray-400">{schema.namespace}</span>
            </label>
          ))}
        </div>
        {selectedKinds.length > 0 && (
          <button
            type="button"
            onClick={() => setSelectedKinds([])}
            className="mt-1 text-blue-600 text-xs hover:text-blue-800"
          >
            Clear all
          </button>
        )}
      </div>

      <div>
        <label htmlFor="deps-depth" className="block font-medium text-gray-600 text-xs">
          Max Depth
        </label>
        <input
          id="deps-depth"
          type="number"
          min={1}
          max={20}
          value={maxDepth}
          onChange={(e) => setMaxDepth(Number(e.target.value))}
          className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
        />
      </div>

      <button
        type="submit"
        disabled={isLoading || !sourceId || selectedKinds.length === 0}
        className="w-full rounded-md bg-amber-600 px-4 py-2 font-medium text-sm text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:bg-gray-300"
      >
        {isLoading ? "Searching..." : "Find Dependencies"}
      </button>
    </form>
  );
}

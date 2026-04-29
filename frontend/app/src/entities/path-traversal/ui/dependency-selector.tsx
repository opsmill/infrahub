import { type FormEvent, useState } from "react";

import { KindMultiSelect } from "@/shared/components/inputs/kind-multi-select";

import { ObjectPicker } from "./object-picker";

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

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (sourceId && selectedKinds.length > 0) {
      onSearch({ sourceId, targetKinds: selectedKinds, maxDepth });
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 p-4">
      <ObjectPicker
        label="Source Object"
        value={sourceId}
        displayLabel={sourceLabel}
        onChange={(id, label) => {
          setSourceId(id);
          setSourceLabel(label);
        }}
      />

      <KindMultiSelect
        value={selectedKinds}
        onChange={setSelectedKinds}
        label="What kinds to find?"
      />

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

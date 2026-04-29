import { useAtomValue } from "jotai";

import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/shared/components/ui/command";
import { classNames } from "@/shared/utils/common";

import { HIDDEN_NAMESPACES } from "@/entities/path-traversal/ui/utils";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

type ChipTone = "blue" | "red";

const TONE_CHIP: Record<ChipTone, string> = {
  blue: "bg-blue-50 text-blue-700",
  red: "bg-red-50 text-red-700",
};

const TONE_CHIP_REMOVE: Record<ChipTone, string> = {
  blue: "text-blue-400 hover:text-blue-600",
  red: "text-red-400 hover:text-red-600",
};

const TONE_CLEAR: Record<ChipTone, string> = {
  blue: "text-blue-500 hover:text-blue-700",
  red: "text-red-500 hover:text-red-700",
};

export interface KindMultiSelectProps {
  value: string[];
  onChange: (kinds: string[]) => void;
  label?: string;
  placeholder?: string;
  showChips?: boolean;
  chipTone?: ChipTone;
  filter?: (namespace: string) => boolean;
  className?: string;
}

const defaultFilter = (namespace: string) => !HIDDEN_NAMESPACES.has(namespace);

export function KindMultiSelect({
  value,
  onChange,
  label,
  placeholder = "Search kinds...",
  showChips = false,
  chipTone = "blue",
  filter = defaultFilter,
  className,
}: KindMultiSelectProps) {
  const nodes = useAtomValue(nodeSchemasAtom).filter((s) => filter(s.namespace as string));

  function toggle(kind: string) {
    onChange(value.includes(kind) ? value.filter((k) => k !== kind) : [...value, kind]);
  }

  return (
    <div className={classNames("space-y-1", className)}>
      {label && (
        <span className="block font-medium text-gray-600 text-xs">
          {label} {value.length > 0 && `(${value.length})`}
        </span>
      )}

      {showChips && value.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {value.map((kind) => {
            const node = nodes.find((n) => n.kind === kind);
            return (
              <span
                key={kind}
                className={classNames(
                  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px]",
                  TONE_CHIP[chipTone]
                )}
              >
                {node?.label ?? kind}
                <button
                  type="button"
                  onClick={() => toggle(kind)}
                  className={TONE_CHIP_REMOVE[chipTone]}
                >
                  ✕
                </button>
              </span>
            );
          })}
          <button
            type="button"
            onClick={() => onChange([])}
            className={classNames("text-[10px]", TONE_CLEAR[chipTone])}
          >
            Clear all
          </button>
        </div>
      )}

      <Command className="rounded-md border border-gray-200">
        <CommandInput placeholder={placeholder} />
        <CommandList className="max-h-32">
          <CommandEmpty>No kinds found</CommandEmpty>
          {nodes.map((s) => {
            const kind = s.kind as string;
            const checked = value.includes(kind);
            return (
              <CommandItem
                key={kind}
                value={kind}
                keywords={[s.label as string, s.namespace as string]}
                onSelect={() => toggle(kind)}
                className="text-xs"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  readOnly
                  className="rounded border-gray-300"
                />
                <span className="truncate">{s.label ?? kind}</span>
                <span className="ml-auto text-gray-400">{s.namespace}</span>
              </CommandItem>
            );
          })}
        </CommandList>
      </Command>

      {!showChips && value.length > 0 && (
        <button
          type="button"
          onClick={() => onChange([])}
          className={classNames("text-xs", TONE_CLEAR[chipTone])}
        >
          Clear
        </button>
      )}
    </div>
  );
}

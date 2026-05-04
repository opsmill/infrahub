import { Button } from "@infrahub/ui";
import { useState } from "react";

import { NodeKindSelect } from "@/shared/components/inputs/node-kind-select";
import { PeerInput } from "@/shared/components/inputs/peer";

import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import type { ModelSchema } from "@/entities/schema/types";

import { isVisibleNamespace } from "./utils";

type ObjectPickerProps = {
  label: string;
  value: string;
  onChange: (id: string) => void;
};

export function ObjectPicker({ label, value, onChange }: ObjectPickerProps) {
  const [selectedKind, setSelectedKind] = useState<string | null>(null);

  // Resolve the display label whenever the picker has a value but no
  // selection in flight. Cheap when cached by React Query.
  const { data: resolved } = useGetObject(
    { objectId: value, objectSchema: { kind: "CoreNode" } as ModelSchema },
    { enabled: !!value }
  );

  const peerValue: Node | null = value
    ? {
        id: value,
        display_label: resolved?.display_label ?? value,
        __typename: selectedKind ?? "",
      }
    : null;

  return (
    <div className="space-y-1.5">
      <span className="block font-medium text-gray-700 text-sm">{label}</span>

      <NodeKindSelect
        value={selectedKind}
        onChange={setSelectedKind}
        filter={isVisibleNamespace}
        className="w-full"
      />

      <PeerInput
        peer={selectedKind ?? "CoreNode"}
        value={peerValue}
        onChange={(node) => onChange(node?.id ?? "")}
        className="w-full"
      />

      {value && (
        <div className="flex items-center gap-2 rounded bg-blue-50 px-2 py-1.5">
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium text-blue-800 text-xs">
              {resolved?.display_label ?? value}
            </div>
            <div className="truncate font-mono text-blue-600 text-xs">{value}</div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onChange("");
              setSelectedKind(null);
            }}
          >
            Clear
          </Button>
        </div>
      )}
    </div>
  );
}

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
  const [pickedNode, setPickedNode] = useState<Node | null>(null);

  // When the form holds an id we didn't pick this session (e.g. a deep link),
  // resolve it through CoreNode so the trigger can render display_label and
  // the concrete __typename.
  const needsResolution = !!value && pickedNode?.id !== value;
  const { data: resolved } = useGetObject(
    { objectId: value, objectSchema: { kind: "CoreNode" } as ModelSchema },
    { enabled: needsResolution }
  );

  const peerValue: Node | null = !value
    ? null
    : pickedNode?.id === value
      ? pickedNode
      : resolved
        ? {
            id: resolved.id ?? value,
            display_label: resolved.display_label ?? value,
            __typename: resolved.__typename ?? "",
          }
        : null;

  function handleKindChange(kind: string | null) {
    setSelectedKind(kind);
    if (kind && pickedNode && pickedNode.__typename !== kind) {
      setPickedNode(null);
      onChange("");
    }
  }

  function handlePeerChange(node: Node | null) {
    setPickedNode(node);
    onChange(node?.id ?? "");
  }

  return (
    <div className="space-y-1.5">
      <span className="block font-medium text-gray-700 text-sm">{label}</span>

      <NodeKindSelect
        value={selectedKind}
        onChange={handleKindChange}
        filter={isVisibleNamespace}
        className="w-full"
      />

      <PeerInput
        peer={selectedKind ?? "CoreNode"}
        value={peerValue}
        onChange={handlePeerChange}
        className="w-full"
      />
    </div>
  );
}

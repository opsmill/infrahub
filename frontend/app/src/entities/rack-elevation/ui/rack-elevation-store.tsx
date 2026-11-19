import React from "react";

import { FAKE_MAPPINGS } from "@/entities/rack-elevation/api/fake-mappings";
import { FAKE_NODES } from "@/entities/rack-elevation/api/fake-nodes";
import { FAKE_SCHEMA } from "@/entities/rack-elevation/api/fake-schema";
import type { RackElevationMapping } from "@/entities/rack-elevation/domain/model/mapping";
import type {
  AttributeUpdate,
  NodeStore,
  Schema,
} from "@/entities/rack-elevation/domain/model/schema";
import { type AttributeChange, diffNodes } from "@/entities/rack-elevation/domain/rules/diff-nodes";

const NODES_KEY = "proto.rack-elevation.nodes";
const MAPPINGS_KEY = "proto.rack-elevation.mappings";

interface RackElevationStore {
  schema: Schema;
  nodes: NodeStore;
  mappings: RackElevationMapping[];
  changes: AttributeChange[];
  updateAttributes: (updates: AttributeUpdate[]) => void;
  discardChanges: () => void;
  saveMapping: (mapping: RackElevationMapping) => void;
  deleteMapping: (mappingId: string) => void;
}

const RackElevationStoreContext = React.createContext<RackElevationStore | null>(null);

function readStorage<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeStorage(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage can be unavailable (private mode); the prototype keeps working in memory.
  }
}

export function RackElevationStoreProvider({ children }: { children: React.ReactNode }) {
  const [nodes, setNodes] = React.useState<NodeStore>(() => readStorage(NODES_KEY, FAKE_NODES));
  const [mappings, setMappings] = React.useState<RackElevationMapping[]>(() =>
    readStorage(MAPPINGS_KEY, FAKE_MAPPINGS)
  );

  React.useEffect(() => writeStorage(NODES_KEY, nodes), [nodes]);
  React.useEffect(() => writeStorage(MAPPINGS_KEY, mappings), [mappings]);

  const updateAttributes = (updates: AttributeUpdate[]) => {
    if (updates.length === 0) return;
    setNodes((current) => {
      const next = { ...current };
      for (const { nodeId, attribute, value } of updates) {
        const node = next[nodeId];
        if (!node) continue;
        next[nodeId] = { ...node, attributes: { ...node.attributes, [attribute]: value } };
      }
      return next;
    });
  };

  const saveMapping = (mapping: RackElevationMapping) => {
    setMappings((current) =>
      current.some((candidate) => candidate.id === mapping.id)
        ? current.map((candidate) => (candidate.id === mapping.id ? mapping : candidate))
        : [...current, mapping]
    );
  };

  const value: RackElevationStore = {
    schema: FAKE_SCHEMA,
    nodes,
    mappings,
    changes: diffNodes(FAKE_NODES, nodes),
    updateAttributes,
    discardChanges: () => setNodes(FAKE_NODES),
    saveMapping,
    deleteMapping: (mappingId) =>
      setMappings((current) => current.filter((candidate) => candidate.id !== mappingId)),
  };

  return <RackElevationStoreContext value={value}>{children}</RackElevationStoreContext>;
}

export function useRackElevationStore(): RackElevationStore {
  const store = React.use(RackElevationStoreContext);
  if (!store)
    throw new Error("useRackElevationStore must be used inside RackElevationStoreProvider");
  return store;
}

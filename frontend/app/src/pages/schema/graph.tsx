import { SchemaVisualizer, type SchemaVisualizerData } from "infrahub-schema-visualizer";
import { useAtomValue } from "jotai";
import { parseAsString, useQueryState } from "nuqs";

import { QSP } from "@/shared/config/qsp";

import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";

function SchemaGraph() {
  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);
  const profiles = useAtomValue(profileSchemasAtom);
  const templates = useAtomValue(templateSchemasAtom);
  const [highlightNodeId, setHighlightNodeId] = useQueryState(QSP.HIGHLIGHT, parseAsString);

  const schemaData: SchemaVisualizerData = { nodes, generics, profiles, templates };

  return (
    <div className="flex min-h-125 flex-1">
      <SchemaVisualizer
        data={schemaData}
        className="flex-1"
        highlightNodeId={highlightNodeId}
        onClearHighlight={() => setHighlightNodeId(null)}
      />
    </div>
  );
}

export function Component() {
  return <SchemaGraph />;
}

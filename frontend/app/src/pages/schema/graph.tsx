import { SchemaVisualizer, type SchemaVisualizerData } from "infrahub-schema-visualizer";
import { useAtomValue } from "jotai";
import { useMemo } from "react";

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

  const schemaData: SchemaVisualizerData = useMemo(
    () => ({ nodes, generics, profiles, templates }),
    [nodes, generics, profiles, templates]
  );

  return (
    <div className="flex min-h-125 flex-1">
      <SchemaVisualizer data={schemaData} className="flex-1" />
    </div>
  );
}

export function Component() {
  return <SchemaGraph />;
}

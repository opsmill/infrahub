import { SchemaVisualizer, type SchemaVisualizerData } from "@infrahub/schema-visualizer";
import { useAtomValue } from "jotai";
import { useMemo } from "react";

import Content from "@/shared/components/layout/content";
import { useTitle } from "@/shared/hooks/useTitle";

import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import { SchemaViewToggle } from "@/entities/schema/ui/schema-view-toggle";

function SchemaGraphPage() {
  useTitle("Schema Graph");

  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);
  const profiles = useAtomValue(profileSchemasAtom);
  const templates = useAtomValue(templateSchemasAtom);

  const schemaData: SchemaVisualizerData = useMemo(
    () => ({ nodes, generics, profiles, templates }),
    [nodes, generics, profiles, templates]
  );

  return (
    <Content.Card className="flex h-[calc(100%-1rem)] flex-col">
      <Content.CardTitle
        title="Schema"
        className="w-full"
        end={<SchemaViewToggle />}
      />

      <div className="flex min-h-125 flex-1">
        <SchemaVisualizer data={schemaData} className="flex-1" />
      </div>
    </Content.Card>
  );
}

export function Component() {
  return <SchemaGraphPage />;
}

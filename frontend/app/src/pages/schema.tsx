import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import { SchemaSelector } from "@/entities/schema/ui/schema-selector";
import { SchemaViewerStack } from "@/entities/schema/ui/schema-viewer";
import Content from "@/shared/components/layout/content";
import { useTitle } from "@/shared/hooks/useTitle";
import { useAtomValue } from "jotai";

function SchemaPage() {
  useTitle("Schema");
  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);
  const profiles = useAtomValue(profileSchemasAtom);

  return (
    <Content.Card className="h-[calc(100%-1rem)] flex flex-col">
      <Content.CardTitle
        title="Schema Visualizer"
        badgeContent={nodes.length + generics.length + profiles.length}
        className="w-full"
      />

      <div className="flex items-stretch grow bg-stone-50">
        <SchemaSelector className="grow max-w-md shrink-0" />
        <SchemaViewerStack className="grow min-w-96 sm:min-w-[520px] max-w-xl max-h-[calc(100vh-145px)] sticky top-2 right-2 m-2" />
      </div>
    </Content.Card>
  );
}

export function Component() {
  return <SchemaPage />;
}

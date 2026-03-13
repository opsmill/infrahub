import { useAtomValue } from "jotai";

import Content from "@/shared/components/layout/content";
import { useTitle } from "@/shared/hooks/useTitle";

import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import { SchemaSelector } from "@/entities/schema/ui/schema-selector";
import { SchemaViewToggle } from "@/entities/schema/ui/schema-view-toggle";
import { SchemaViewerStack } from "@/entities/schema/ui/schema-viewer";

function SchemaPage() {
  useTitle("Schema");
  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);
  const profiles = useAtomValue(profileSchemasAtom);

  return (
    <Content.Card className="flex h-[calc(100%-1rem)] flex-col">
      <Content.CardTitle
        title="Schema"
        badgeContent={nodes.length + generics.length + profiles.length}
        className="w-full"
        end={<SchemaViewToggle />}
      />

      <div className="flex grow items-stretch bg-stone-50">
        <SchemaSelector className="max-w-md shrink-0 grow" />
        <SchemaViewerStack className="sticky top-2 right-2 m-2 max-h-[calc(100vh-145px)] min-w-96 max-w-xl grow sm:min-w-130" />
      </div>
    </Content.Card>
  );
}

export function Component() {
  return <SchemaPage />;
}

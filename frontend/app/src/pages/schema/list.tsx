import { SchemaSelector } from "@/entities/schema/ui/schema-selector";
import { SchemaViewerStack } from "@/entities/schema/ui/schema-viewer";

function SchemaList() {
  return (
    <div className="flex grow items-stretch bg-stone-50">
      <SchemaSelector className="max-w-md shrink-0 grow" />
      <SchemaViewerStack className="sticky top-2 right-2 m-2 max-h-[calc(100vh-145px)] min-w-96 max-w-xl grow sm:min-w-130" />
    </div>
  );
}

export function Component() {
  return <SchemaList />;
}

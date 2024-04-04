import { useAtomValue } from "jotai";
import { useTitle } from "../../hooks/useTitle";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { SchemaSelector } from "./schema-selector";
import { SchemaViewerStack } from "./schema-viewer";
import { Badge } from "../../components/ui/badge";
import Content from "../layout/content";

export default function SchemaPage() {
  useTitle("Schema");
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);

  return (
    <Content>
      <Content.Title
        title={
          <div className="flex items-center">
            <h1 className="mr-2 truncate">Schema Visualizer</h1>
            <Badge>{nodes.length + generics.length}</Badge>
          </div>
        }
      />

      <div className="flex items-stretch min-h-full">
        <SchemaSelector className="flex-grow max-w-md shrink-0" />
        <SchemaViewerStack className="flex-grow min-w-96 sm:min-w-[520px] max-w-xl max-h-[calc(100vh-145px)] sticky top-2 right-2 m-2" />
      </div>
    </Content>
  );
}

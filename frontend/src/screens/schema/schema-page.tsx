import { useAtomValue } from "jotai";
import { useTitle } from "../../hooks/useTitle";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { SchemaPageHeader } from "./schema-page-header";
import { SchemaSelector } from "./schema-selector";
import { SchemaViewer } from "./schema-viewer";
import { Badge } from "../../components/ui/badge";

export default function SchemaPage() {
  useTitle("Schema");
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);

  return (
    <>
      <SchemaPageHeader
        title={
          <>
            Schema Visualizer <Badge>{nodes.length + generics.length}</Badge>
          </>
        }
      />

      <div className="flex gap-2 items-start relative">
        <SchemaSelector className="flex-grow" />
        <SchemaViewer />
      </div>
    </>
  );
}
